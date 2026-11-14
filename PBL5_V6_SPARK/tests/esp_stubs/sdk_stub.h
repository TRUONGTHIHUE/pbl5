#ifndef PBL5_TEST_SDK_STUB_H
#define PBL5_TEST_SDK_STUB_H
/* HOST TEST DOUBLE ONLY. These declarations do NOT validate real ESP-IDF ABI. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdarg.h>
#define BIT0 1U
#define BIT1 2U
#define BIT2 4U
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(x) (x)
typedef void *QueueHandle_t;
typedef void *EventGroupHandle_t;
typedef uint32_t EventBits_t;
QueueHandle_t xQueueCreate(unsigned,unsigned);
int xQueueReceive(QueueHandle_t,void*,uint32_t);
int xQueueSend(QueueHandle_t,const void*,uint32_t);
int xQueueOverwrite(QueueHandle_t,const void*);
EventGroupHandle_t xEventGroupCreate(void);
EventBits_t xEventGroupGetBits(EventGroupHandle_t);
EventBits_t xEventGroupSetBits(EventGroupHandle_t,EventBits_t);
EventBits_t xEventGroupClearBits(EventGroupHandle_t,EventBits_t);
int xTaskCreate(void(*)(void*),const char*,unsigned,void*,unsigned,void*);
void vTaskDelay(unsigned);
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_WIFI_NOT_STARTED 2
#define ESP_ERR_NVS_NO_FREE_PAGES 3
#define ESP_ERR_NVS_NEW_VERSION_FOUND 4
#define ESP_ERROR_CHECK(x) do {if ((x)!=ESP_OK) abort();} while(0)
static inline __attribute__((format(printf,2,3))) void test_log(const char *tag,const char *format,...) {(void)tag;(void)format;}
#define ESP_LOGI(...) test_log(__VA_ARGS__)
#define ESP_LOGW(...) test_log(__VA_ARGS__)
#define ESP_LOGE(...) test_log(__VA_ARGS__)
#define ESP_LOG_WARN 2
void esp_log_level_set(const char*,int);
typedef const char *esp_event_base_t;
#define WIFI_EVENT ((esp_event_base_t)1)
#define IP_EVENT ((esp_event_base_t)2)
#define ESP_EVENT_ANY_ID -1
#define WIFI_EVENT_STA_STOP 1
#define WIFI_EVENT_STA_DISCONNECTED 2
#define IP_EVENT_STA_GOT_IP 3
#define IP_EVENT_STA_LOST_IP 4
esp_err_t esp_event_loop_create_default(void);
esp_err_t esp_event_handler_register(esp_event_base_t,int32_t,void(*)(void*,esp_event_base_t,int32_t,void*),void*);
typedef struct {uint16_t reason;} wifi_event_sta_disconnected_t;
typedef struct {unsigned char ssid[33];} wifi_ap_record_t;
typedef struct {uint32_t addr;} esp_ip4_addr_t;
typedef struct {esp_ip4_addr_t ip, netmask, gw;} esp_netif_ip_info_t;
typedef void esp_netif_t;
#define IPSTR "%u.%u.%u.%u"
#define IP2STR(p) (unsigned)((uint8_t*)&((p)->addr))[0],(unsigned)((uint8_t*)&((p)->addr))[1],(unsigned)((uint8_t*)&((p)->addr))[2],(unsigned)((uint8_t*)&((p)->addr))[3]
esp_err_t esp_netif_init(void);
esp_netif_t *esp_netif_create_default_wifi_sta(void);
esp_err_t esp_netif_get_ip_info(esp_netif_t*,esp_netif_ip_info_t*);
typedef struct {int dummy;} wifi_init_config_t;
#define WIFI_INIT_CONFIG_DEFAULT() ((wifi_init_config_t){0})
#define WIFI_STORAGE_RAM 0
#define WIFI_MODE_STA 1
#define WIFI_IF_STA 0
#define WIFI_AUTH_WPA2_PSK 3
#define WIFI_AUTH_OPEN 0
typedef struct {struct {unsigned char ssid[32],password[64];struct {bool capable;} pmf_cfg;struct {int authmode;} threshold;} sta;} wifi_config_t;
esp_err_t esp_wifi_init(const wifi_init_config_t*);
esp_err_t esp_wifi_set_storage(int);
esp_err_t esp_wifi_set_mode(int);
esp_err_t esp_wifi_set_config(int,const wifi_config_t*);
esp_err_t esp_wifi_sta_get_ap_info(wifi_ap_record_t*);
esp_err_t esp_wifi_start(void);
esp_err_t esp_wifi_stop(void);
esp_err_t esp_wifi_connect(void);
esp_err_t esp_wifi_disconnect(void);
int64_t esp_timer_get_time(void);
uint32_t esp_random(void);
esp_err_t nvs_flash_init(void);
esp_err_t nvs_flash_erase(void);
#define UART_NUM_0 0
int uart_read_bytes(int,void*,unsigned,unsigned);
esp_err_t uart_driver_install(int,int,int,int,void*,int);
esp_err_t uart_set_baudrate(int,int);
typedef struct cJSON {char *valuestring;double valuedouble;} cJSON;
cJSON *cJSON_CreateObject(void);
cJSON *cJSON_AddObjectToObject(cJSON*,const char*);
void cJSON_AddStringToObject(cJSON*,const char*,const char*);
void cJSON_AddNumberToObject(cJSON*,const char*,double);
void cJSON_AddBoolToObject(cJSON*,const char*,int);
char *cJSON_PrintUnformatted(const cJSON*);
void cJSON_free(void*);
void cJSON_Delete(cJSON*);
cJSON *cJSON_ParseWithOpts(const char*,const char**,int);
cJSON *cJSON_GetObjectItemCaseSensitive(const cJSON*,const char*);
int cJSON_IsString(const cJSON*);
int cJSON_IsNumber(const cJSON*);
#define SPI2_HOST 2
#define RC522_PICC_STATE_ACTIVE 1
#define RC522_EVENT_PICC_STATE_CHANGED 1
#define CONFIG_PBL5_RC522_MISO 19
#define CONFIG_PBL5_RC522_MOSI 23
#define CONFIG_PBL5_RC522_SCK 18
#define CONFIG_PBL5_RC522_CS 21
#define CONFIG_PBL5_RC522_RST 22
typedef void *rc522_driver_handle_t;
typedef void *rc522_handle_t;
typedef struct {int miso_io_num,mosi_io_num,sclk_io_num,quadwp_io_num,quadhd_io_num;} spi_bus_config_t;
typedef struct {int host_id;spi_bus_config_t *bus_config;struct {int spics_io_num,clock_speed_hz;} dev_config;int rst_io_num;} rc522_spi_config_t;
typedef struct {rc522_driver_handle_t driver;} rc522_config_t;
typedef struct {struct {uint8_t value[10];uint8_t length;} uid;int state;} rc522_picc_t;
typedef struct {rc522_picc_t *picc;} rc522_picc_state_changed_event_t;
esp_err_t rc522_spi_create(const rc522_spi_config_t*,rc522_driver_handle_t*);
esp_err_t rc522_driver_install(rc522_driver_handle_t);
esp_err_t rc522_create(const rc522_config_t*,rc522_handle_t*);
esp_err_t rc522_register_events(rc522_handle_t,int,void(*)(void*,esp_event_base_t,int32_t,void*),void*);
esp_err_t rc522_start(rc522_handle_t);
#endif
