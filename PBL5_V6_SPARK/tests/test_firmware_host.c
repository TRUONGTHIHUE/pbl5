/* Executes actual main.c controller functions against FAKE ESP/FreeRTOS APIs.
 * This tests application decisions, not ESP-IDF compilation or physical radio.
 */
#include "../main/main.c"
#include <assert.h>
static EventBits_t fake_bits;
static bool fake_link;
static unsigned stops, starts, connects;
static wifi_config_t fake_config;
EventBits_t xEventGroupGetBits(EventGroupHandle_t h) {(void)h;return fake_bits;}
EventBits_t xEventGroupSetBits(EventGroupHandle_t h,EventBits_t b) {(void)h;return fake_bits|=b;}
EventBits_t xEventGroupClearBits(EventGroupHandle_t h,EventBits_t b) {(void)h;EventBits_t old=fake_bits;fake_bits&=~b;return old;}
esp_err_t esp_wifi_sta_get_ap_info(wifi_ap_record_t *ap) {if(!fake_link)return ESP_FAIL;memset(ap,0,sizeof(*ap));memcpy(ap->ssid,fake_config.sta.ssid,32);return ESP_OK;}
esp_err_t esp_netif_get_ip_info(esp_netif_t *s,esp_netif_ip_info_t *ip) {(void)s;memset(ip,0,sizeof(*ip));ip->ip.addr=fake_link?0x0201a8c0U:0;return ESP_OK;}
esp_err_t esp_wifi_set_config(int i,const wifi_config_t *c) {(void)i;fake_config=*c;return ESP_OK;}
esp_err_t esp_wifi_start(void) {starts++;return ESP_OK;}
esp_err_t esp_wifi_stop(void) {stops++;fake_link=false;atomic_store(&ip_available,false);fake_bits|=EV_STOP;return ESP_OK;}
esp_err_t esp_wifi_connect(void) {connects++;return ESP_OK;}
esp_err_t esp_wifi_disconnect(void) {fake_link=false;atomic_store(&ip_available,false);return ESP_OK;}
uint32_t esp_random(void) {return 12345U;}
static void simulated_ip(void) {fake_link=true;atomic_store(&ip_available,true);fake_bits|=EV_IP;}
static void reset_state(void) {
    memset(&state,0,sizeof(state));state.phase="idle";state.code="";state.action="none";
    strcpy(state.boot,"1111111111111111");strcpy(state.client,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    fake_bits=0;fake_link=false;stops=starts=connects=0;atomic_store(&ip_available,false);
}
static command_t credentials(const char *store) {
    command_t c={.kind=CMD_WIFI,.generation=state.generation};
    strcpy(c.boot,state.boot);strcpy(c.client,state.client);strcpy(c.uid,state.uid);
    strcpy(c.store_id,store);strcpy(c.store_name,store);strcpy(c.owner_uid,"owner-test");
    strcpy(c.wifi.ssid,"TEST_NETWORK");strcpy(c.wifi.password,"TEST_PASSWORD_123");return c;
}
int main(void) {
    reset_state();start_scan("CD4B1E03",0);command_t a=credentials("shop-a");handle_command(&a,1);
    assert(starts==1&&stops==0&&!state.ready);simulated_ip();network_tick(2);assert(state.ready);
    start_scan("C79A0C03",1001);assert(!state.ready&&state.store_id[0]==0);
    command_t b=credentials("shop-b");handle_command(&b,1002);
    assert(state.ready&&state.reuse_count==1&&stops==0&&starts==1&&strcmp(state.store_id,"shop-b")==0);
    puts("PASS same Wi-Fi: new store, no stop/start");
    start_scan("C79A0C03",2002);b=credentials("shop-b");strcpy(b.wifi.password,"CHANGED_PASSWORD");handle_command(&b,2003);
    assert(!state.ready&&stops==1&&state.net==NET_STOPPING);network_tick(2004);assert(starts==2);
    network_tick(28000);assert(!state.ready&&strcmp(state.phase,"wifi_failed")==0);
    assert(strcmp(state.store_id,"shop-b")==0);puts("PASS changed/wrong password: reconfigure, timeout, no old store fallback");
    simulated_ip();network_tick(28001);assert(state.ready);
    fake_link=false;wifi_event(NULL,WIFI_EVENT,WIFI_EVENT_STA_DISCONNECTED,NULL);network_tick(29000);
    assert(!state.ready&&state.net==NET_RETRY_WAIT);unsigned before=connects;network_tick(30001);network_tick(31002);assert(connects>before);
    simulated_ip();network_tick(31003);assert(state.ready&&strcmp(state.store_id,"shop-b")==0);
    puts("PASS network loss/reconnect: readiness gated, selected store preserved");
    start_scan("CD4B1E03",33000);a=credentials("shop-a");start_scan("C79A0C03",33001);handle_command(&a,33002);
    assert(!state.selected&&state.store_id[0]==0);puts("PASS late credentials from previous RFID rejected");
    b=credentials("shop-b");strcpy(b.boot,"2222222222222222");handle_command(&b,33003);assert(!state.selected);
    puts("PASS different boot nonce rejected");
    b=credentials("shop-b");handle_command(&b,33004);network_tick(33005);simulated_ip();network_tick(33006);
    command_t hello={.kind=CMD_HELLO};strcpy(hello.client,"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");uint32_t old=state.generation;
    handle_command(&hello,34000);assert(!state.ready&&state.generation==old+1&&strcmp(state.phase,"waiting_credentials")==0);
    puts("PASS Python reopen: fresh generation and backend authorization required");
    b=credentials("shop-b");handle_command(&b,34001);command_t cancel=b;cancel.kind=CMD_CANCEL;handle_command(&cancel,34002);
    assert(!state.selected&&!state.ready&&state.store_id[0]==0);puts("PASS backend cancel clears selected store");
    start_scan("C79A0C03",36000);b=credentials("shop-b");handle_command(&b,36001);
    state.net=NET_RETRY_WAIT;state.next_attempt=36002;state.driver_started=true;
    fake_link=false;atomic_store(&ip_available,false);fake_bits|=EV_STOP;before=starts;
    network_tick(36003);network_tick(37004);assert(starts>before);puts("PASS delayed STOP event recovers driver state");
    puts("HOST TEST DOUBLE ONLY: no actual ESP-IDF build, Wi-Fi AP, USB, or RC522 used.");
    return 0;
}
