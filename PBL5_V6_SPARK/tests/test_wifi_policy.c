#include "wifi_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    wifi_credentials_t a = {"TEST_NETWORK", "TEST_PASSWORD_123"};
    wifi_credentials_t b = a;
    assert(wifi_credentials_valid(&a));
    assert(wifi_can_reuse(&a, &b, true, true, "TEST_NETWORK"));
    assert(!wifi_can_reuse(&a, &b, true, false, "TEST_NETWORK"));
    assert(!wifi_can_reuse(&a, &b, true, true, "OTHER_NETWORK"));
    strcpy(b.password, "CHANGED_PASSWORD");
    assert(!wifi_can_reuse(&a, &b, true, true, "TEST_NETWORK"));
    strcpy(b.password, "short"); assert(!wifi_credentials_valid(&b));
    b.password[0] = 0; assert(wifi_credentials_valid(&b));
    b.ssid[0] = 0; assert(!wifi_credentials_valid(&b));
    char uid[21]; uint8_t bytes[10] = {0xcd,0x4b,0x1e,0x03};
    assert(uid_to_hex(bytes, 4, uid) && strcmp(uid, "CD4B1E03") == 0);
    assert(uid_to_hex(bytes, 7, uid) && strlen(uid) == 14);
    assert(uid_to_hex(bytes, 10, uid) && strlen(uid) == 20);
    assert(!uid_to_hex(bytes, 5, uid));
    assert(wifi_retry_delay_ms(0) == 1000 && wifi_retry_delay_ms(99) == 16000);
    secure_zero(&a, sizeof(a)); assert(a.ssid[0] == 0 && a.password[0] == 0);
    puts("PASS: 14 native C policy assertions. NOT an ESP-IDF build or RF Wi-Fi test.");
    return 0;
}
