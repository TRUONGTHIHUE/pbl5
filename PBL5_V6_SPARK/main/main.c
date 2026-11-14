/* PBL5_UNIFIED_V6. Single-owner controller; callbacks never perform network work.
 * Protocol v2 is intentionally incompatible with V3/V4/V5 Python programs.
 * Wi-Fi secrets arrive only via trusted local USB and remain in RAM.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <inttypes.h>
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "cJSON.h"
#include "rc522.h"
#include "rc522_picc.h"
#include "driver/rc522_spi.h"
#include "wifi_policy.h"

#define PROTOCOL_VERSION 2
#define EV_STOP BIT0
#define EV_DROP BIT1
#define EV_IP BIT2
#define CONNECT_MS 25000ULL
#define CREDENTIAL_MS 45000ULL
#define PC_LEASE_MS 15000ULL
static const char *TAG = "PBL5";
static QueueHandle_t scan_queue, command_queue;
static EventGroupHandle_t wifi_events;
static atomic_bool ip_available;
static atomic_uint disconnect_reason;
static esp_netif_t *station;
static rc522_driver_handle_t rfid_driver;
static rc522_handle_t scanner;

typedef struct { char uid[21]; } scan_t;
typedef enum {CMD_HELLO, CMD_STATUS, CMD_WIFI, CMD_CANCEL, CMD_RETRY} command_kind_t;
typedef struct {
    command_kind_t kind;
    char client[33], boot[17], uid[21];
    uint32_t generation;
    wifi_credentials_t wifi;
    char store_id[256], store_name[256], owner_uid[129];
} command_t;
typedef enum {NET_IDLE, NET_STOPPING, NET_CONNECTING, NET_RETRY_WAIT} net_stage_t;
/* All fields below are read/written ONLY by controller_task. */
static struct {
    char boot[17], client[33], uid[21];
    uint32_t generation, reuse_count, switch_count, link_seq;
    char store_id[256], store_name[256], owner_uid[129];
    wifi_credentials_t target, applied;
    bool selected, applied_valid, driver_started, ready, dirty;
    char actual_ssid[33], ip[20];
    const char *phase, *code, *action;
    net_stage_t net;
    uint64_t last_pc, scan_at, credentials_until, stop_until, connect_until, next_attempt, last_emit;
    unsigned retries;
} state;
static uint64_t now_ms(void) { return (uint64_t)esp_timer_get_time() / 1000ULL; }
static void set_phase(const char *phase, const char *code) { state.phase = phase; state.code = code; state.dirty = true; }
static void clear_selection(void) {
    state.selected = state.ready = false;
    state.store_id[0] = state.store_name[0] = state.owner_uid[0] = 0;
    secure_zero(&state.target, sizeof(state.target));
}
static bool physical_link(void) {
    state.actual_ssid[0] = state.ip[0] = 0;
    if (!state.driver_started || !atomic_load(&ip_available)) return false;
    wifi_ap_record_t ap = {0}; esp_netif_ip_info_t ip = {0};
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK || esp_netif_get_ip_info(station, &ip) != ESP_OK || ip.ip.addr == 0) return false;
    memcpy(state.actual_ssid, ap.ssid, 32); state.actual_ssid[32] = 0;
    snprintf(state.ip, sizeof(state.ip), IPSTR, IP2STR(&ip.ip));
    return true;
}
static void emit_state(void) {
    bool connected = physical_link();
    bool valid_ready = state.selected && state.ready && wifi_can_reuse(&state.applied, &state.target,
                                       state.applied_valid, connected, state.actual_ssid);
    cJSON *j = cJSON_CreateObject();
    if (!j) return;
    cJSON_AddNumberToObject(j, "v", PROTOCOL_VERSION);
    cJSON_AddStringToObject(j, "firmware", "PBL5_UNIFIED_V6");
    cJSON_AddStringToObject(j, "boot_id", state.boot);
    cJSON_AddStringToObject(j, "client_id", state.client);
    cJSON_AddNumberToObject(j, "generation", state.generation);
    cJSON_AddStringToObject(j, "rfid_uid", state.uid);
    cJSON_AddStringToObject(j, "store_id", state.store_id);
    cJSON_AddStringToObject(j, "store_name", state.store_name);
    cJSON_AddStringToObject(j, "owner_uid", state.owner_uid);
    cJSON_AddStringToObject(j, "phase", state.phase);
    cJSON_AddStringToObject(j, "code", state.code);
    cJSON_AddBoolToObject(j, "ready", valid_ready);
    cJSON *w = cJSON_AddObjectToObject(j, "wifi");
    if (w) {
        cJSON_AddBoolToObject(w, "connected", connected);
        cJSON_AddStringToObject(w, "ssid", state.actual_ssid);
        cJSON_AddStringToObject(w, "ip", state.ip);
        cJSON_AddNumberToObject(w, "reason", atomic_load(&disconnect_reason));
        cJSON_AddStringToObject(w, "action", state.action);
        cJSON_AddNumberToObject(w, "reuse_count", state.reuse_count);
        cJSON_AddNumberToObject(w, "switch_count", state.switch_count);
        cJSON_AddNumberToObject(w, "link_seq", state.link_seq);
    }
    char *serialized = cJSON_PrintUnformatted(j);
    if (serialized) { printf("\n@STATE:%s\n", serialized); fflush(stdout); cJSON_free(serialized); }
    cJSON_Delete(j); state.last_emit = now_ms(); state.dirty = false;
}
static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_STOP) {
        atomic_store(&ip_available, false); xEventGroupSetBits(wifi_events, EV_STOP);
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *e = data;
        atomic_store(&ip_available, false);
        if (e) atomic_store(&disconnect_reason, e->reason);
        xEventGroupSetBits(wifi_events, EV_DROP);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        atomic_store(&ip_available, true); xEventGroupSetBits(wifi_events, EV_IP);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_LOST_IP) {
        atomic_store(&ip_available, false); xEventGroupSetBits(wifi_events, EV_DROP);
    }
}
static void on_card(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg; (void)base; (void)id;
    const rc522_picc_state_changed_event_t *e = data;
    scan_t scan = {0};
    if (e && e->picc && e->picc->state == RC522_PICC_STATE_ACTIVE &&
        uid_to_hex(e->picc->uid.value, e->picc->uid.length, scan.uid)) xQueueOverwrite(scan_queue, &scan);
}
static bool copy_json_string(const cJSON *root, const char *key, char *out, size_t capacity, bool empty) {
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(root, key);
    if (!cJSON_IsString(v) || !v->valuestring) return false;
    size_t n = strlen(v->valuestring);
    if (n >= capacity || (!empty && n == 0)) return false;
    for (size_t i = 0; i < n; i++) if ((unsigned char)v->valuestring[i] < 32 || v->valuestring[i] == 127) return false;
    memcpy(out, v->valuestring, n + 1); return true;
}
static bool is_hex(const char *s, size_t length) {
    if (strlen(s) != length) return false;
    for (size_t i = 0; i < length; i++)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f') || (s[i] >= 'A' && s[i] <= 'F'))) return false;
    return true;
}
static void parse_command(char *line) {
    if (strncmp(line, "@CMD:", 5) != 0 || strstr(line, "\\u0000")) return;
    cJSON *j = cJSON_ParseWithOpts(line + 5, NULL, true);
    if (!j) return;
    command_t m = {0}; char kind[16]; bool valid = false;
    const cJSON *version = cJSON_GetObjectItemCaseSensitive(j, "v");
    if (!cJSON_IsNumber(version) || version->valuedouble != PROTOCOL_VERSION ||
        !copy_json_string(j, "command", kind, sizeof(kind), false) ||
        !copy_json_string(j, "client_id", m.client, sizeof(m.client), false) || !is_hex(m.client, 32)) goto done;
    if (strcmp(kind, "hello") == 0) { m.kind = CMD_HELLO; valid = true; goto done; }
    if (strcmp(kind, "status") == 0) { m.kind = CMD_STATUS; valid = true; goto done; }
    const cJSON *g = cJSON_GetObjectItemCaseSensitive(j, "generation");
    if (!cJSON_IsNumber(g) || !(g->valuedouble >= 0 && g->valuedouble <= UINT32_MAX) ||
        g->valuedouble != (double)(uint32_t)g->valuedouble ||
        !copy_json_string(j, "boot_id", m.boot, sizeof(m.boot), false) || !is_hex(m.boot, 16)) goto done;
    m.generation = (uint32_t)g->valuedouble;
    if (strcmp(kind, "cancel") == 0) { m.kind = CMD_CANCEL; valid = true; goto done; }
    if (strcmp(kind, "retry") == 0) { m.kind = CMD_RETRY; valid = true; goto done; }
    if (strcmp(kind, "wifi") != 0) goto done;
    m.kind = CMD_WIFI;
    valid = copy_json_string(j, "rfid_uid", m.uid, sizeof(m.uid), false) &&
        copy_json_string(j, "store_id", m.store_id, sizeof(m.store_id), false) &&
        copy_json_string(j, "store_name", m.store_name, sizeof(m.store_name), false) &&
        copy_json_string(j, "owner_uid", m.owner_uid, sizeof(m.owner_uid), false) &&
        copy_json_string(j, "ssid", m.wifi.ssid, sizeof(m.wifi.ssid), false) &&
        copy_json_string(j, "password", m.wifi.password, sizeof(m.wifi.password), true) && wifi_credentials_valid(&m.wifi);
done:
    if (valid && xQueueSend(command_queue, &m, pdMS_TO_TICKS(20)) != pdTRUE) ESP_LOGW(TAG, "serial_queue_full");
    cJSON *secret = cJSON_GetObjectItemCaseSensitive(j, "password");
    if (cJSON_IsString(secret) && secret->valuestring) secure_zero(secret->valuestring, strlen(secret->valuestring));
    secure_zero(&m, sizeof(m)); cJSON_Delete(j);
}
static void serial_task(void *arg) {
    (void)arg; char line[2048]; size_t used = 0; bool overflow = false;
    for (;;) {
        uint8_t c;
        if (uart_read_bytes(UART_NUM_0, &c, 1, pdMS_TO_TICKS(100)) <= 0) continue;
        if (c == '\r') continue;
        if (c == '\n') {
            if (!overflow) { line[used] = 0; parse_command(line); }
            secure_zero(line, sizeof(line)); used = 0; overflow = false;
        } else if (used < sizeof(line) - 1) line[used++] = (char)c;
        else overflow = true;
    }
}
static void start_scan(const char *uid, uint64_t now) {
    char copy[21]; snprintf(copy, sizeof(copy), "%s", uid);
    clear_selection(); snprintf(state.uid, sizeof(state.uid), "%s", copy);
    state.generation++;
    if (state.generation == 0) {
        snprintf(state.boot, sizeof(state.boot), "%08" PRIx32 "%08" PRIx32, esp_random(), esp_random());
        state.generation = 1;
    }
    state.scan_at = now; state.credentials_until = now + CREDENTIAL_MS;
    state.action = "none"; set_phase("waiting_credentials", "");
    ESP_LOGI(TAG, "SCAN generation=%" PRIu32 " uid=%s", state.generation, state.uid);
}
static void connection_failed(const char *code, uint64_t now) {
    state.ready = false; state.net = NET_RETRY_WAIT; state.next_attempt = now + 15000ULL;
    atomic_store(&ip_available, false);
    if (state.driver_started) (void)esp_wifi_disconnect();
    set_phase("wifi_failed", code);
    ESP_LOGW(TAG, "WIFI_FAILED code=%s reason=%u", code, atomic_load(&disconnect_reason));
}
static void start_desired_network(uint64_t now) {
    if (!state.selected) { state.net = NET_IDLE; return; }
    wifi_config_t config = {0};
    memcpy(config.sta.ssid, state.target.ssid, strlen(state.target.ssid));
    memcpy(config.sta.password, state.target.password, strlen(state.target.password));
    config.sta.pmf_cfg.capable = true;
    config.sta.threshold.authmode = state.target.password[0] ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    esp_err_t err = esp_wifi_set_config(WIFI_IF_STA, &config);
    secure_zero(&config, sizeof(config));
    if (err != ESP_OK) { connection_failed("wifi_set_config_failed", now); return; }
    secure_zero(&state.applied, sizeof(state.applied)); state.applied = state.target; state.applied_valid = true;
    atomic_store(&ip_available, false); atomic_store(&disconnect_reason, 0);
    xEventGroupClearBits(wifi_events, EV_DROP | EV_IP);
    err = esp_wifi_start();
    if (err != ESP_OK) { connection_failed("wifi_start_failed", now); return; }
    state.driver_started = true;
    err = esp_wifi_connect();
    if (err != ESP_OK) { connection_failed("wifi_connect_failed", now); return; }
    state.net = NET_CONNECTING; state.connect_until = now + CONNECT_MS;
    state.next_attempt = now + 5000ULL; state.retries = 0; set_phase("connecting", "");
}
static void configure_target(uint64_t now) {
    bool connected = physical_link();
    if (state.net != NET_STOPPING && wifi_can_reuse(&state.applied, &state.target, state.applied_valid, connected, state.actual_ssid)) {
        xEventGroupClearBits(wifi_events, EV_DROP | EV_IP);
        state.net = NET_IDLE; state.ready = true; state.action = "reused"; state.reuse_count++;
        set_phase("ready", ""); ESP_LOGI(TAG, "WIFI_REUSED store=%s", state.store_id); return;
    }
    state.ready = false; state.action = "reconfigured";
    if (state.net == NET_STOPPING) return; // A later card replaces the target while stop is in progress.
    state.switch_count++; atomic_store(&ip_available, false);
    xEventGroupClearBits(wifi_events, EV_STOP | EV_DROP | EV_IP);
    if (state.driver_started) {
        esp_err_t err = esp_wifi_stop();
        if (err == ESP_OK) { state.net = NET_STOPPING; state.stop_until = now + 3000ULL; set_phase("switching", ""); return; }
        if (err != ESP_ERR_WIFI_NOT_STARTED) { connection_failed("wifi_stop_failed", now); return; }
        state.driver_started = false;
    }
    start_desired_network(now);
}
static void handle_command(const command_t *m, uint64_t now) {
    if (m->kind == CMD_HELLO) {
        if (strcmp(state.client, m->client) != 0) {
            snprintf(state.client, sizeof(state.client), "%s", m->client);
            clear_selection();
            if (state.uid[0]) start_scan(state.uid, now);
            else set_phase("idle", "");
        }
        state.last_pc = now; state.dirty = true; return;
    }
    if (strcmp(state.client, m->client) != 0) return;
    state.last_pc = now;
    if (m->kind == CMD_STATUS) { state.dirty = true; return; }
    if (strcmp(state.boot, m->boot) != 0 || state.generation != m->generation) return;
    if (m->kind == CMD_CANCEL) { clear_selection(); set_phase("backend_error", "backend_rejected_or_timeout"); return; }
    if (m->kind == CMD_RETRY) { if (state.uid[0]) start_scan(state.uid, now); return; }
    if (m->kind != CMD_WIFI || strcmp(state.uid, m->uid) != 0 || strcmp(state.phase, "waiting_credentials") != 0) return;
    state.target = m->wifi;
    snprintf(state.store_id, sizeof(state.store_id), "%s", m->store_id);
    snprintf(state.store_name, sizeof(state.store_name), "%s", m->store_name);
    snprintf(state.owner_uid, sizeof(state.owner_uid), "%s", m->owner_uid);
    state.selected = true; configure_target(now);
}
static void network_tick(uint64_t now) {
    EventBits_t bits = xEventGroupGetBits(wifi_events);
    if ((bits & EV_STOP) && state.net != NET_STOPPING) {
        xEventGroupClearBits(wifi_events, EV_STOP);
        state.driver_started = false; atomic_store(&ip_available, false);
        if (state.selected) { state.net = NET_RETRY_WAIT; state.next_attempt = now; }
    }
    if (state.net == NET_STOPPING) {
        if (bits & EV_STOP) {
            xEventGroupClearBits(wifi_events, EV_STOP | EV_DROP | EV_IP);
            state.driver_started = false; start_desired_network(now);
        } else if (now >= state.stop_until) connection_failed("wifi_stop_timeout", now);
        return;
    }
    if (!state.selected) {
        if (state.net == NET_RETRY_WAIT) state.net = NET_IDLE;
        return; // Never reconnect or reactivate a previously selected store.
    }
    if ((bits & EV_DROP) && state.ready) {
        state.ready = false; state.link_seq++; state.action = "reconnecting";
        state.net = NET_RETRY_WAIT; state.next_attempt = now + 1000ULL;
        set_phase("reconnecting", "wifi_lost");
    }
    bool linked = physical_link() && wifi_can_reuse(&state.applied, &state.target, state.applied_valid, true, state.actual_ssid);
    if (linked) {
        if (!state.ready) { state.ready = true; state.link_seq++; set_phase("ready", "");
            ESP_LOGI(TAG, "WIFI_READY store=%s ip=%s action=%s", state.store_id, state.ip, state.action); }
        state.net = NET_IDLE; xEventGroupClearBits(wifi_events, EV_DROP | EV_IP); return;
    }
    if (state.ready) {
        state.ready = false; state.link_seq++; state.action = "reconnecting";
        state.net = NET_RETRY_WAIT; state.next_attempt = now + 1000ULL;
        set_phase("reconnecting", "wifi_lost");
    }
    if (state.net == NET_RETRY_WAIT && now >= state.next_attempt) {
        state.action = "reconnecting";
        if (!state.driver_started || !wifi_credentials_equal(&state.applied, &state.target)) { configure_target(now); return; }
        state.net = NET_CONNECTING; state.connect_until = now + CONNECT_MS;
        state.next_attempt = now; state.retries = 0; set_phase("reconnecting", "");
    }
    if (state.net == NET_CONNECTING) {
        if (now >= state.connect_until) { connection_failed("connect_timeout", now); return; }
        if (bits & EV_DROP) {
            xEventGroupClearBits(wifi_events, EV_DROP);
            state.next_attempt = now + wifi_retry_delay_ms(state.retries++);
            state.dirty = true;
        }
        if (now >= state.next_attempt) {
            (void)esp_wifi_connect();
            state.next_attempt = now + wifi_retry_delay_ms(state.retries++);
        }
    }
}
static void controller_task(void *arg) {
    (void)arg;
    snprintf(state.boot, sizeof(state.boot), "%08" PRIx32 "%08" PRIx32, esp_random(), esp_random());
    state.phase = "idle"; state.code = ""; state.action = "none"; state.dirty = true;
    for (;;) {
        uint64_t now = now_ms(); scan_t scan;
        if (xQueueReceive(scan_queue, &scan, 0) == pdTRUE &&
            (strcmp(scan.uid, state.uid) != 0 || now - state.scan_at >= 1000ULL)) start_scan(scan.uid, now);
        command_t m;
        for (unsigned i = 0; i < 4 && xQueueReceive(command_queue, &m, 0) == pdTRUE; i++) {
            handle_command(&m, now); secure_zero(&m, sizeof(m));
        }
        if (state.client[0] && now - state.last_pc > PC_LEASE_MS) {
            state.client[0] = 0; clear_selection(); set_phase("pc_disconnected", "pc_lease_expired");
        }
        if (strcmp(state.phase, "waiting_credentials") == 0 && now >= state.credentials_until) {
            clear_selection(); set_phase("credentials_timeout", "no_credentials_received");
        }
        network_tick(now);
        if (state.dirty || now - state.last_emit >= 1000ULL) emit_state();
        vTaskDelay(pdMS_TO_TICKS(30));
    }
}
void app_main(void) {
    ESP_LOGI(TAG, "VERSION: PBL5_UNIFIED_V6 protocol=2; no hardcoded Wi-Fi/Firebase credentials");
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase()); err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err); ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_events = xEventGroupCreate(); scan_queue = xQueueCreate(1, sizeof(scan_t));
    command_queue = xQueueCreate(4, sizeof(command_t));
    if (!wifi_events || !scan_queue || !command_queue) { ESP_LOGE(TAG, "out_of_memory"); return; }
    ESP_ERROR_CHECK(esp_netif_init()); station = esp_netif_create_default_wifi_sta();
    if (!station) { ESP_LOGE(TAG, "netif_failed"); return; }
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT(); ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    esp_log_level_set("wifi", ESP_LOG_WARN);
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 4096, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_set_baudrate(UART_NUM_0, 115200));
    if (xTaskCreate(serial_task, "serial_rx", 6144, NULL, 3, NULL) != pdPASS ||
        xTaskCreate(controller_task, "controller", 12288, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "task_create_failed"); return;
    }
    static spi_bus_config_t bus = {.miso_io_num = CONFIG_PBL5_RC522_MISO,
        .mosi_io_num = CONFIG_PBL5_RC522_MOSI, .sclk_io_num = CONFIG_PBL5_RC522_SCK,
        .quadwp_io_num = -1, .quadhd_io_num = -1};
    rc522_spi_config_t driver_config = {.host_id = SPI2_HOST, .bus_config = &bus,
        .dev_config = {.spics_io_num = CONFIG_PBL5_RC522_CS, .clock_speed_hz = 400000},
        .rst_io_num = CONFIG_PBL5_RC522_RST};
    ESP_ERROR_CHECK(rc522_spi_create(&driver_config, &rfid_driver));
    ESP_ERROR_CHECK(rc522_driver_install(rfid_driver));
    rc522_config_t config = {.driver = rfid_driver};
    ESP_ERROR_CHECK(rc522_create(&config, &scanner));
    ESP_ERROR_CHECK(rc522_register_events(scanner, RC522_EVENT_PICC_STATE_CHANGED, on_card, NULL));
    ESP_ERROR_CHECK(rc522_start(scanner));
    ESP_LOGI(TAG, "RC522_READY: open unified Python then scan card");
}
