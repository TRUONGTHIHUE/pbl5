#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdatomic.h>
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "cJSON.h"
#include "rc522.h"
#include "rc522_picc.h"
#include "driver/rc522_spi.h"
#include "store_codec.h"

static const char *TAG = "STORE_RFID";
#define WIFI_READY BIT0
#define WIFI_STOPPED BIT1
static EventGroupHandle_t wifi_events;
static QueueHandle_t scan_queue, credentials_queue;
static SemaphoreHandle_t store_mutex;
static rc522_driver_handle_t driver;
static rc522_handle_t scanner;
static atomic_bool wifi_configured;
static atomic_bool switching;
static uint32_t generation;
static store_info_t current_store;
static bool current_store_valid;
static char wifi_phase[48] = "bootstrap";
static esp_netif_t *station;
typedef struct { char uid[RFID_UID_TEXT_SIZE]; uint32_t generation; } scan_message_t;
typedef struct {
    uint32_t generation;
    char ssid[33];
    char password[65];
    char store_id[256];
    char store_name[256];
} credentials_message_t;

// All protocol output holds store_mutex, so generation cannot change mid-response.
static void emit(const char *prefix, cJSON *root)
{
    if (!root) return;
    char *text = cJSON_PrintUnformatted(root);
    if (text) {
        if (strlen(text) <= 24000) { printf("\n%s%s\n", prefix, text); fflush(stdout); }
        cJSON_free(text);
    }
    cJSON_Delete(root);
}
static void store_event(const char *kind, const scan_message_t *m, const store_info_t *s)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "event", kind);
    cJSON_AddNumberToObject(j, "generation", m->generation);
    cJSON_AddStringToObject(j, "rfid_uid", m->uid);
    if (s) {
        cJSON_AddStringToObject(j, "store_id", s->document_id);
        cJSON_AddStringToObject(j, "store_name", s->name);
        cJSON_AddBoolToObject(j, "wifi_credentials_loaded", s->wifi_present);
        cJSON_AddStringToObject(j, "store_ssid", s->wifi_ssid);
    }
    emit("@STORE:", j);
}
static void wifi_status_locked(void)
{
    wifi_ap_record_t ap = {0};
    esp_netif_ip_info_t ip = {0};
    bool connected = wifi_configured && (xEventGroupGetBits(wifi_events) & WIFI_READY)
        && esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
    char ssid[33] = {0}, ip_text[20] = "";
    if (connected) {
        memcpy(ssid, ap.ssid, 32);
        if (station && esp_netif_get_ip_info(station, &ip) == ESP_OK)
            snprintf(ip_text, sizeof(ip_text), IPSTR, IP2STR(&ip.ip));
    }
    cJSON *j = cJSON_CreateObject();
    cJSON_AddNumberToObject(j, "generation", generation);
    cJSON_AddStringToObject(j, "phase", wifi_phase);
    cJSON_AddBoolToObject(j, "connected", connected);
    cJSON_AddStringToObject(j, "ssid", ssid);
    cJSON_AddStringToObject(j, "ip", ip_text);
    cJSON_AddBoolToObject(j, "store_wifi_connected", connected && current_store_valid
        && current_store.wifi_present && strcmp(ssid, current_store.wifi_ssid) == 0);
    emit("@WIFI:", j);
}
static bool is_current(uint32_t gen)
{
    xSemaphoreTake(store_mutex, portMAX_DELAY);
    bool yes = generation == gen;
    xSemaphoreGive(store_mutex);
    return yes;
}
static void phase(uint32_t gen, const char *text)
{
    xSemaphoreTake(store_mutex, portMAX_DELAY);
    if (generation == gen) {
        snprintf(wifi_phase, sizeof(wifi_phase), "%s", text);
        wifi_status_locked();
    }
    xSemaphoreGive(store_mutex);
}
static void wifi_event(
    void *arg,
    esp_event_base_t base,
    int32_t id,
    void *data
)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        if (!atomic_load(&switching)) {
            esp_wifi_connect();
        }

    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_STOP) {
        xEventGroupClearBits(wifi_events, WIFI_READY);
        xEventGroupSetBits(wifi_events, WIFI_STOPPED);

    } else if (base == WIFI_EVENT &&
               id == WIFI_EVENT_STA_DISCONNECTED) {

        // BỔ SUNG: in nguyên nhân mất kết nối, không in mật khẩu.
        const wifi_event_sta_disconnected_t *disconnected =
            (const wifi_event_sta_disconnected_t *)data;

        if (disconnected != NULL) {
            ESP_LOGW(
                TAG,
                "WIFI_DISCONNECTED: reason=%u, switching=%d",
                (unsigned)disconnected->reason,
                (int)atomic_load(&switching)
            );
        }

        xEventGroupClearBits(wifi_events, WIFI_READY);

        xSemaphoreTake(store_mutex, portMAX_DELAY);
        snprintf(wifi_phase, sizeof(wifi_phase), "disconnected");
        xSemaphoreGive(store_mutex);

        if (!atomic_load(&switching)) {
            esp_wifi_connect();
        }

    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(wifi_events, WIFI_READY);

        xSemaphoreTake(store_mutex, portMAX_DELAY);
        snprintf(wifi_phase, sizeof(wifi_phase), "ip_ready");
        xSemaphoreGive(store_mutex);

        ESP_LOGI(
            TAG,
            "Wi-Fi da co IP; chua ket luan Firebase truy cap duoc"
        );
    }
}
static void wifi_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    station = esp_netif_create_default_wifi_sta();
    if (!station) {
        ESP_LOGE(TAG, "Khong tao duoc Wi-Fi STA");
        return;
    }
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                               wifi_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    wifi_configured = true;
    ESP_LOGI(TAG, "V5: Cho Wi-Fi tu Python; KHONG co mat khau Firebase/Wi-Fi trong firmware.");
}

static bool connect_wifi(const char *ssid, const char *password)
{
    if (!wifi_configured || !ssid[0] || strlen(ssid) > 32 || strlen(password) > 64) {
        ESP_LOGE(TAG, "WIFI_SWITCH: cau hinh Wi-Fi khong hop le (khong in mat khau)");
        return false;
    }
    ESP_LOGI(TAG, "WIFI_SWITCH: target_ssid=%s, password_length=%u",
             ssid, (unsigned)strlen(password));
    wifi_config_t cfg = {0};
    memcpy(cfg.sta.ssid, ssid, strlen(ssid));
    memcpy(cfg.sta.password, password, strlen(password));
    cfg.sta.pmf_cfg.capable = true;
    atomic_store(&switching, true);
    xEventGroupClearBits(wifi_events, WIFI_STOPPED | WIFI_READY);
    esp_err_t err = esp_wifi_stop();
    if (err == ESP_OK && !(xEventGroupWaitBits(wifi_events, WIFI_STOPPED, pdTRUE, pdTRUE,
                                              pdMS_TO_TICKS(3000)) & WIFI_STOPPED)) {
        ESP_LOGE(TAG, "WIFI_SWITCH: timeout cho WIFI_EVENT_STA_STOP");
        atomic_store(&switching, false); return false;
    }
    if (err != ESP_OK && err != ESP_ERR_WIFI_NOT_STARTED) {
        ESP_LOGE(TAG, "WIFI_SWITCH: esp_wifi_stop: %s", esp_err_to_name(err));
        atomic_store(&switching, false); return false;
    }
    err = esp_wifi_set_config(WIFI_IF_STA, &cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "WIFI_SWITCH: esp_wifi_set_config: %s", esp_err_to_name(err));
        atomic_store(&switching, false); return false;
    }
    atomic_store(&switching, false);
    err = esp_wifi_start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "WIFI_SWITCH: esp_wifi_start: %s", esp_err_to_name(err));
        return false;
    }
    bool connected = (xEventGroupWaitBits(wifi_events, WIFI_READY, pdFALSE, pdTRUE,
                                          pdMS_TO_TICKS(20000)) & WIFI_READY) != 0;
    ESP_LOGI(TAG, "WIFI_SWITCH: target_ssid=%s, got_ip=%s",
             ssid, connected ? "YES" : "NO");
    return connected;
}
static void report_scan_error(const scan_message_t *m)
{
    xSemaphoreTake(store_mutex, portMAX_DELAY);
    if (m->generation == generation) { current_store_valid = false; store_event("error", m, NULL); }
    xSemaphoreGive(store_mutex);
}
static void on_card(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    rc522_picc_state_changed_event_t *event = data;
    if (!event || !event->picc || event->picc->state != RC522_PICC_STATE_ACTIVE) return;
    scan_message_t m = {0};
    if (!uid_to_hex(event->picc->uid.value, event->picc->uid.length, m.uid)) return;
    xSemaphoreTake(store_mutex, portMAX_DELAY);
    m.generation = ++generation;
    current_store_valid = false;
    memset(&current_store, 0, sizeof(current_store));
    store_event("scanning", &m, NULL);
    xQueueOverwrite(scan_queue, &m);
    xSemaphoreGive(store_mutex);
}
static void process_scan(const scan_message_t *m)
{
    credentials_message_t credentials = {0};
    phase(m->generation, "waiting_pc_credentials");
    ESP_LOGI(TAG, "Cho backend xac thuc RFID=%s va Python gui Wi-Fi (45 giay)", m->uid);
    if (xQueueReceive(credentials_queue, &credentials, pdMS_TO_TICKS(45000)) != pdTRUE) {
        ESP_LOGE(TAG, "Het 45 giay. Kiem tra Python/COM4/backend va quet lai.");
        report_scan_error(m);
        return;
    }
    if (credentials.generation != m->generation || !is_current(m->generation)) {
        if (credentials.generation > m->generation)
            xQueueOverwrite(credentials_queue, &credentials);
        memset(&credentials, 0, sizeof(credentials));
        return;
    }
    phase(m->generation, "store_connecting");
    bool connected = connect_wifi(credentials.ssid, credentials.password);
    memset(credentials.password, 0, sizeof(credentials.password));
    if (!connected || !is_current(m->generation)) {
        ESP_LOGE(TAG, "Khong ket noi duoc Wi-Fi cua hang (SSID/mat khau/2.4 GHz)");
        report_scan_error(m);
        memset(&credentials, 0, sizeof(credentials));
        return;
    }
    xSemaphoreTake(store_mutex, portMAX_DELAY);
    if (m->generation == generation) {
        memset(&current_store, 0, sizeof(current_store));
        snprintf(current_store.document_id, sizeof(current_store.document_id), "%s", credentials.store_id);
        snprintf(current_store.name, sizeof(current_store.name), "%s", credentials.store_name);
        snprintf(current_store.rfid_uid, sizeof(current_store.rfid_uid), "%s", m->uid);
        snprintf(current_store.wifi_ssid, sizeof(current_store.wifi_ssid), "%s", credentials.ssid);
        current_store.wifi_present = true;
        // Authorization is performed on the PC backend, never by trusting RFID alone.
        current_store_valid = true;
        snprintf(wifi_phase, sizeof(wifi_phase), "store_wifi_connected");
        store_event("identified", m, &current_store);
        store_event("ready", m, &current_store);
        wifi_status_locked();
    }
    xSemaphoreGive(store_mutex);
    memset(&credentials, 0, sizeof(credentials));
}
static void rfid_worker(void *arg)
{
    for (;;) {
        scan_message_t scan;
        if (xQueueReceive(scan_queue, &scan, portMAX_DELAY) == pdTRUE)
            process_scan(&scan);
    }
}
static void command_line(char *line)
{
    if (strncmp(line, "@CMD:", 5)) return;
    cJSON *j = cJSON_Parse(line + 5);
    const cJSON *cmd = cJSON_GetObjectItemCaseSensitive(j, "command");
    if (!cJSON_IsString(cmd)) { cJSON_Delete(j); return; }
    if (!strcmp(cmd->valuestring, "status")) {
        xSemaphoreTake(store_mutex, portMAX_DELAY);
        if (current_store_valid) {
            scan_message_t m = {.generation = generation};
            snprintf(m.uid, sizeof(m.uid), "%s", current_store.rfid_uid);
            store_event("ready", &m, &current_store);
        }
        wifi_status_locked();
        xSemaphoreGive(store_mutex);
    } else if (!strcmp(cmd->valuestring, "wifi")) {
        const cJSON *g = cJSON_GetObjectItemCaseSensitive(j, "generation");
        const cJSON *s = cJSON_GetObjectItemCaseSensitive(j, "ssid");
        const cJSON *p = cJSON_GetObjectItemCaseSensitive(j, "password");
        const cJSON *store_id = cJSON_GetObjectItemCaseSensitive(j, "store_id");
        const cJSON *store_name = cJSON_GetObjectItemCaseSensitive(j, "store_name");
        if (cJSON_IsNumber(g) && g->valuedouble >= 0 && g->valuedouble <= UINT32_MAX &&
            cJSON_IsString(s) && cJSON_IsString(p) &&
            cJSON_IsString(store_id) && cJSON_IsString(store_name) &&
            strlen(s->valuestring) >= 1 && strlen(s->valuestring) <= 32 &&
            strlen(p->valuestring) <= 64 &&
            strlen(store_id->valuestring) >= 1 && strlen(store_id->valuestring) <= 255 &&
            strlen(store_name->valuestring) <= 255) {
            credentials_message_t credentials = {0};
            credentials.generation = (uint32_t)g->valuedouble;
            snprintf(credentials.ssid, sizeof(credentials.ssid), "%s", s->valuestring);
            snprintf(credentials.password, sizeof(credentials.password), "%s", p->valuestring);
            snprintf(credentials.store_id, sizeof(credentials.store_id), "%s", store_id->valuestring);
            snprintf(credentials.store_name, sizeof(credentials.store_name), "%s", store_name->valuestring);
            xSemaphoreTake(store_mutex, portMAX_DELAY);
            if (generation == credentials.generation) {
                xQueueOverwrite(credentials_queue, &credentials);
                ESP_LOGI(TAG, "Da nhan SSID=%s cho store=%s (khong in mat khau)",
                         credentials.ssid, credentials.store_id);
            } else {
                ESP_LOGW(TAG, "Bo qua lenh Wi-Fi cua lan quet cu");
            }
            xSemaphoreGive(store_mutex);
            memset(&credentials, 0, sizeof(credentials));
        } else {
            ESP_LOGW(TAG, "Lenh wifi sai/khong du truong store_id, store_name, ssid, password");
        }
    }
    cJSON_Delete(j);
}
static void serial_task(void *arg)
{
    char line[2048]; size_t used = 0; bool overflow = false;
    for (;;) {
        uint8_t c;
        if (uart_read_bytes(UART_NUM_0, &c, 1, pdMS_TO_TICKS(100)) <= 0) continue;
        if (c == '\r') continue;
        if (c == '\n') {
            if (!overflow) { line[used] = 0; command_line(line); }
            used = 0; overflow = false;
        } else if (used < sizeof(line)-1) line[used++] = (char)c;
        else overflow = true;
    }
}
void app_main(void)
{
    // Dòng đánh dấu để xác nhận đang chạy đúng code mới.
    ESP_LOGW("VERSION", "RFID_MULTI_STORE_V5");

    esp_err_t err = nvs_flash_init();

    if (
        err == ESP_ERR_NVS_NO_FREE_PAGES ||
        err == ESP_ERR_NVS_NEW_VERSION_FOUND
    ) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }

    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(
        esp_event_loop_create_default()
    );

    wifi_events = xEventGroupCreate();

    scan_queue = xQueueCreate(
        1,
        sizeof(scan_message_t)
    );

    store_mutex = xSemaphoreCreateMutex();
    credentials_queue = xQueueCreate(1, sizeof(credentials_message_t));

    if (!wifi_events || !scan_queue || !store_mutex || !credentials_queue) {
        ESP_LOGE(TAG, "Khong tao duoc event group/queue/mutex");
        return;
    }

    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 4096, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_set_baudrate(UART_NUM_0, 115200));
    if (xTaskCreate(serial_task, "serial_rx", 6144, NULL, 3, NULL) != pdPASS) return;
    wifi_start();

    // Sơ đồ RC522:
    // SDA/SS -> GPIO21
    // SCK    -> GPIO18
    // MOSI   -> GPIO23
    // MISO   -> GPIO19
    // RST    -> GPIO22
    // 3.3V   -> 3V3
    // GND    -> GND
    // IRQ    -> Không nối

    static spi_bus_config_t bus = {
        .miso_io_num = 19,
        .mosi_io_num = 23,
        .sclk_io_num = 18,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
    };

    rc522_spi_config_t driver_config = {
        .host_id = SPI2_HOST,
        .bus_config = &bus,

        .dev_config = {
            .spics_io_num = 21,
            .clock_speed_hz = 400000,
        },

        .rst_io_num = 22,
    };

    ESP_ERROR_CHECK(
        rc522_spi_create(&driver_config, &driver)
    );

    ESP_ERROR_CHECK(
        rc522_driver_install(driver)
    );

    rc522_config_t config = {
        .driver = driver
    };

    ESP_ERROR_CHECK(
        rc522_create(&config, &scanner)
    );

    ESP_ERROR_CHECK(
        rc522_register_events(
            scanner,
            RC522_EVENT_PICC_STATE_CHANGED,
            on_card,
            NULL
        )
    );

    esp_err_t rc522_err = rc522_start(scanner);

    if (rc522_err != ESP_OK) {
        ESP_LOGE(
            TAG,
            "RC522 khoi dong that bai: %s. "
            "Kiem tra day SPI, RST va nguon 3.3V.",
            esp_err_to_name(rc522_err)
        );
        return;
    }

    if (
        xTaskCreate(
            rfid_worker,
            "rfid_worker",
            8192,
            NULL,
            4,
            NULL
        ) != pdPASS
    ) {
        ESP_LOGE(TAG, "Khong tao duoc task RFID worker");
        return;
    }

    ESP_LOGI(TAG, "RC522 san sang. Dua the lai gan.");
    ESP_LOGI(TAG, "Thao the ra truoc khi quet lai.");
    ESP_LOGI(TAG, "Chay Python V5 tren PC co Internet truoc khi quet the.");
}