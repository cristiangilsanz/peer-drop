#include "handlers.h"

#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "audit.h"
#include "protocol.h"
#include "registry.h"

#define MAX_FIELDS 3

typedef void (*Run)(int socket, const char *address, char fields[][FIELD_CAPACITY]);

typedef struct {
    const char *name;
    uint8_t error_code;
    size_t field_count;
    int file_field;
    Run run;
} Command;

static void run_register(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    write_code(socket, registry_register(fields[0]));
}

static void run_unregister(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    write_code(socket, registry_unregister(fields[0]));
}

static void run_connect(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    char *end = NULL;
    errno = 0;
    long port = strtol(fields[1], &end, 10);
    bool valid = errno == 0 && *end == '\0' && port > 0 && port <= 65535;
    write_code(socket, valid ? registry_connect(fields[0], address, (int)port) : CONNECT_ERROR);
}

static void run_disconnect(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    write_code(socket, registry_disconnect(fields[0]));
}

static void run_publish(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    write_code(socket, registry_publish(fields[0], fields[1], fields[2]));
}

static void run_delete(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    write_code(socket, registry_delete(fields[0], fields[1]));
}

static void run_list_users(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    PeerList peers;
    ListUsersResult result = registry_list_users(fields[0], &peers);
    write_code(socket, result);
    if (result == LIST_USERS_OK) {
        write_number(socket, (long)peers.count);
        for (size_t i = 0; i < peers.count; i++) {
            write_field(socket, peers.items[i].name);
            write_field(socket, peers.items[i].address);
            write_number(socket, peers.items[i].port);
        }
    }
    peer_list_free(&peers);
}

static void run_list_content(int socket, const char *address, char fields[][FIELD_CAPACITY]) {
    (void)address;
    FileList files;
    ListContentResult result = registry_list_content(fields[0], fields[1], &files);
    write_code(socket, result);
    if (result == LIST_CONTENT_OK) {
        write_number(socket, (long)files.count);
        for (size_t i = 0; i < files.count; i++) {
            write_field(socket, files.names[i]);
        }
    }
    file_list_free(&files);
}

static const Command COMMANDS[] = {
    {"REGISTER", REGISTER_ERROR, 1, -1, run_register},
    {"UNREGISTER", UNREGISTER_ERROR, 1, -1, run_unregister},
    {"CONNECT", CONNECT_ERROR, 2, -1, run_connect},
    {"DISCONNECT", DISCONNECT_ERROR, 1, -1, run_disconnect},
    {"PUBLISH", PUBLISH_ERROR, 3, 1, run_publish},
    {"DELETE", DELETE_ERROR, 2, 1, run_delete},
    {"LIST_USERS", LIST_USERS_ERROR, 1, -1, run_list_users},
    {"LIST_CONTENT", LIST_CONTENT_ERROR, 2, -1, run_list_content},
};

static const uint8_t UNKNOWN_COMMAND_CODE = 4;

static const Command *find_command(const char *name) {
    for (size_t i = 0; i < sizeof(COMMANDS) / sizeof(COMMANDS[0]); i++) {
        if (strcmp(COMMANDS[i].name, name) == 0) {
            return &COMMANDS[i];
        }
    }
    return NULL;
}

void handle_client(int socket, const char *address) {
    char name[FIELD_CAPACITY];
    if (!read_field(socket, name)) {
        return;
    }
    const Command *command = find_command(name);
    if (command == NULL) {
        write_code(socket, UNKNOWN_COMMAND_CODE);
        return;
    }
    char timestamp[FIELD_CAPACITY];
    char fields[MAX_FIELDS][FIELD_CAPACITY];
    bool complete = read_field(socket, timestamp);
    for (size_t i = 0; complete && i < command->field_count; i++) {
        complete = read_field(socket, fields[i]) && fields[i][0] != '\0';
    }
    if (!complete) {
        write_code(socket, command->error_code);
        return;
    }
    printf("OPERATION %s FROM %s\n", command->name, fields[0]);
    command->run(socket, address, fields);
    const char *file = command->file_field >= 0 ? fields[command->file_field] : "";
    audit_operation(fields[0], command->name, file, timestamp);
}
