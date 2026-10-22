#ifndef PEER_DROP_PROTOCOL_H
#define PEER_DROP_PROTOCOL_H

#include <stdbool.h>
#include <stdint.h>

#define FIELD_CAPACITY 256

bool read_field(int socket, char field[FIELD_CAPACITY]);
bool write_field(int socket, const char *text);
bool write_code(int socket, uint8_t code);
bool write_number(int socket, long number);

#endif
