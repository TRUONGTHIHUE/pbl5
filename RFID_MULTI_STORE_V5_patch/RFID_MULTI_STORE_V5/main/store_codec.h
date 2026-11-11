#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "cJSON.h"
#define RFID_UID_TEXT_SIZE 21

typedef struct {
    char document_id[1537];
    char store_code[1537];
    char name[601];
    char wifi_ssid[33];
    char wifi_password[65];
    bool wifi_present;
    char rfid_uid[RFID_UID_TEXT_SIZE];
} store_info_t;

bool uid_to_hex(const uint8_t *bytes, size_t length, char out[RFID_UID_TEXT_SIZE]);
bool normalize_uid(const char *text, char out[RFID_UID_TEXT_SIZE]);
// 1: unique match; 0: not found; 2: duplicates; -1: bad response/oversize field.
int store_parse_query(const cJSON *response, const char *uid, store_info_t *out);
