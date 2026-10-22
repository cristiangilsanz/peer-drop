#ifndef PEER_DROP_REGISTRY_H
#define PEER_DROP_REGISTRY_H

#include <stddef.h>

#include "protocol.h"

#define ADDRESS_CAPACITY 46

typedef enum { REGISTER_OK, REGISTER_TAKEN, REGISTER_ERROR } RegisterResult;
typedef enum { UNREGISTER_OK, UNREGISTER_UNKNOWN, UNREGISTER_ERROR } UnregisterResult;
typedef enum { CONNECT_OK, CONNECT_UNKNOWN, CONNECT_ALREADY_CONNECTED, CONNECT_ERROR } ConnectResult;
typedef enum { DISCONNECT_OK, DISCONNECT_UNKNOWN, DISCONNECT_NOT_CONNECTED, DISCONNECT_ERROR } DisconnectResult;
typedef enum { PUBLISH_OK, PUBLISH_UNKNOWN, PUBLISH_NOT_CONNECTED, PUBLISH_DUPLICATE, PUBLISH_ERROR } PublishResult;
typedef enum { DELETE_OK, DELETE_UNKNOWN, DELETE_NOT_CONNECTED, DELETE_MISSING, DELETE_ERROR } DeleteResult;
typedef enum { LIST_USERS_OK, LIST_USERS_UNKNOWN, LIST_USERS_NOT_CONNECTED, LIST_USERS_ERROR } ListUsersResult;
typedef enum {
    LIST_CONTENT_OK,
    LIST_CONTENT_UNKNOWN,
    LIST_CONTENT_NOT_CONNECTED,
    LIST_CONTENT_TARGET_UNKNOWN,
    LIST_CONTENT_ERROR
} ListContentResult;

typedef struct {
    char name[FIELD_CAPACITY];
    char address[ADDRESS_CAPACITY];
    int port;
} Peer;

typedef struct {
    Peer *items;
    size_t count;
} PeerList;

typedef struct {
    char (*names)[FIELD_CAPACITY];
    size_t count;
} FileList;

RegisterResult registry_register(const char *user);
UnregisterResult registry_unregister(const char *user);
ConnectResult registry_connect(const char *user, const char *address, int port);
DisconnectResult registry_disconnect(const char *user);
PublishResult registry_publish(const char *user, const char *file, const char *description);
DeleteResult registry_delete(const char *user, const char *file);
ListUsersResult registry_list_users(const char *user, PeerList *peers);
ListContentResult registry_list_content(const char *user, const char *target, FileList *files);
void registry_clear(void);

void peer_list_free(PeerList *peers);
void file_list_free(FileList *files);

#endif
