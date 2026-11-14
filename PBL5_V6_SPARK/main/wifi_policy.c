#include "wifi_policy.h"
#include <string.h>
#include <ctype.h>
void secure_zero(void *data, size_t length) {
    volatile unsigned char *p = data;
    while (length--) *p++ = 0;
}
bool wifi_credentials_valid(const wifi_credentials_t *c) {
    if (!c || !memchr(c->ssid, 0, sizeof(c->ssid)) || !memchr(c->password, 0, sizeof(c->password))) return false;
    size_t s = strlen(c->ssid), p = strlen(c->password);
    if (s == 0 || s > 32) return false;
    for (size_t i = 0; i < s; i++) if ((unsigned char)c->ssid[i] < 32 || c->ssid[i] == 127) return false;
    if (p == 0) return true;
    if (p == 64) {
        for (size_t i = 0; i < p; i++) if (!isxdigit((unsigned char)c->password[i])) return false;
        return true;
    }
    if (p < 8 || p > 63) return false;
    for (size_t i = 0; i < p; i++) if ((unsigned char)c->password[i] < 32 || (unsigned char)c->password[i] > 126) return false;
    return true;
}
bool wifi_credentials_equal(const wifi_credentials_t *a, const wifi_credentials_t *b) {
    return a && b && strcmp(a->ssid, b->ssid) == 0 && strcmp(a->password, b->password) == 0;
}
bool wifi_can_reuse(const wifi_credentials_t *applied, const wifi_credentials_t *requested,
                    bool valid, bool connected, const char *actual) {
    return valid && connected && actual && wifi_credentials_equal(applied, requested) && strcmp(actual, requested->ssid) == 0;
}
uint32_t wifi_retry_delay_ms(unsigned attempt) {
    if (attempt > 4) attempt = 4;
    return 1000U << attempt;
}
bool uid_to_hex(const uint8_t *bytes, size_t length, char output[21]) {
    if (!bytes || !output || (length != 4 && length != 7 && length != 10)) return false;
    const char *hex = "0123456789ABCDEF";
    for (size_t i = 0; i < length; i++) { output[2*i] = hex[bytes[i] >> 4]; output[2*i+1] = hex[bytes[i] & 15]; }
    output[2*length] = 0; return true;
}
