#ifndef PBL5_WIFI_POLICY_H
#define PBL5_WIFI_POLICY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct { char ssid[33]; char password[65]; } wifi_credentials_t;
bool wifi_credentials_valid(const wifi_credentials_t *c);
bool wifi_credentials_equal(const wifi_credentials_t *a, const wifi_credentials_t *b);
bool wifi_can_reuse(const wifi_credentials_t *applied, const wifi_credentials_t *requested,
                    bool applied_valid, bool connected_with_ip, const char *actual_ssid);
uint32_t wifi_retry_delay_ms(unsigned attempt);
bool uid_to_hex(const uint8_t *bytes, size_t length, char output[21]);
void secure_zero(void *data, size_t length);
#endif
