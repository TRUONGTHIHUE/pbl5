#include "store_codec.h"
#include <ctype.h>
#include <string.h>

bool uid_to_hex(const uint8_t *bytes, size_t length, char out[RFID_UID_TEXT_SIZE])
{
    out[0] = '\0';
    if (!bytes || (length != 4 && length != 7 && length != 10)) return false;
    const char *hex = "0123456789ABCDEF";
    for (size_t i = 0; i < length; i++) {
        out[2*i] = hex[bytes[i] >> 4];
        out[2*i+1] = hex[bytes[i] & 15];
    }
    out[2*length] = '\0';
    return true;
}
bool normalize_uid(const char *text, char out[RFID_UID_TEXT_SIZE])
{
    size_t n = 0;
    out[0] = '\0';
    if (!text) return false;
    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        if (isspace(*p) || *p == ':' || *p == '-') continue;
        if (!isxdigit(*p) || n >= RFID_UID_TEXT_SIZE - 1) { out[0] = '\0'; return false; }
        out[n++] = (char)toupper(*p);
    }
    out[n] = '\0';
    if (n != 8 && n != 14 && n != 20) { out[0] = '\0'; return false; }
    return true;
}
static const char *field_string(const cJSON *fields, const char *key)
{
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(cJSON_GetObjectItemCaseSensitive(fields, key), "stringValue");
    return cJSON_IsString(value) ? value->valuestring : "";
}
static bool copy_text(char *dst, size_t size, const char *text)
{
    if (strlen(text) >= size) return false;
    memcpy(dst, text, strlen(text) + 1); return true;
}
int store_parse_query(const cJSON *response, const char *uid, store_info_t *out)
{
    memset(out, 0, sizeof(*out));
    if (!cJSON_IsArray(response)) return -1;
    int count = 0;
    const cJSON *row;
    cJSON_ArrayForEach(row, response) {
        const cJSON *document = cJSON_GetObjectItemCaseSensitive(row, "document");
        if (!document) continue; // Empty query still contains a readTime row.
        const cJSON *fields = cJSON_GetObjectItemCaseSensitive(document, "fields");
        char normalized[RFID_UID_TEXT_SIZE];
        if (!normalize_uid(field_string(fields, "rfidId"), normalized) || strcmp(normalized, uid)) continue;
        if (++count > 1) { memset(out, 0, sizeof(*out)); return 2; }
        const cJSON *path = cJSON_GetObjectItemCaseSensitive(document, "name");
        if (!cJSON_IsString(path)) return -1;
        const char *id = strrchr(path->valuestring, '/');
        if (!id || !id[1]) return -1;
        if (!copy_text(out->document_id, sizeof(out->document_id), id + 1) ||
            !copy_text(out->store_code, sizeof(out->store_code), field_string(fields, "storeId")) ||
            !copy_text(out->name, sizeof(out->name), field_string(fields, "storeName"))) return -1;
        const cJSON *ssid = cJSON_GetObjectItemCaseSensitive(cJSON_GetObjectItemCaseSensitive(fields, "wifiSSID"), "stringValue");
        const cJSON *password = cJSON_GetObjectItemCaseSensitive(cJSON_GetObjectItemCaseSensitive(fields, "wifiPassword"), "stringValue");
        out->wifi_present = cJSON_IsString(ssid) && ssid->valuestring[0] && cJSON_IsString(password)
            && copy_text(out->wifi_ssid, sizeof(out->wifi_ssid), ssid->valuestring)
            && copy_text(out->wifi_password, sizeof(out->wifi_password), password->valuestring);
        copy_text(out->rfid_uid, sizeof(out->rfid_uid), normalized);
    }
    return count;
}
