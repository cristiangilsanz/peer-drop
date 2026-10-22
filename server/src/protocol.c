#include "protocol.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

static bool write_all(int socket, const void *data, size_t size) {
    const char *bytes = data;
    while (size > 0) {
        ssize_t written = write(socket, bytes, size);
        if (written <= 0) {
            return false;
        }
        bytes += written;
        size -= (size_t)written;
    }
    return true;
}

bool read_field(int socket, char field[FIELD_CAPACITY]) {
    for (size_t length = 0; length < FIELD_CAPACITY; length++) {
        char byte;
        if (read(socket, &byte, 1) != 1) {
            return false;
        }
        field[length] = byte;
        if (byte == '\0') {
            return true;
        }
    }
    field[FIELD_CAPACITY - 1] = '\0';
    return false;
}

bool write_field(int socket, const char *text) {
    return write_all(socket, text, strlen(text) + 1);
}

bool write_code(int socket, uint8_t code) {
    return write_all(socket, &code, 1);
}

bool write_number(int socket, long number) {
    char text[32];
    snprintf(text, sizeof(text), "%ld", number);
    return write_field(socket, text);
}
