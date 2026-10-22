#include "registry.h"

#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char name[FIELD_CAPACITY];
    char description[FIELD_CAPACITY];
} SharedFile;

typedef struct {
    char name[FIELD_CAPACITY];
    char address[ADDRESS_CAPACITY];
    int port;
    bool connected;
    SharedFile *files;
    size_t file_count;
} User;

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static User *users;
static size_t user_count;

static bool valid_name(const char *name) {
    return name != NULL && name[0] != '\0' && strlen(name) < FIELD_CAPACITY;
}

static void copy_text(char *target, const char *source, size_t capacity) {
    strncpy(target, source, capacity - 1);
    target[capacity - 1] = '\0';
}

static User *find_user(const char *name) {
    for (size_t i = 0; i < user_count; i++) {
        if (strcmp(users[i].name, name) == 0) {
            return &users[i];
        }
    }
    return NULL;
}

static SharedFile *find_file(User *user, const char *name) {
    for (size_t i = 0; i < user->file_count; i++) {
        if (strcmp(user->files[i].name, name) == 0) {
            return &user->files[i];
        }
    }
    return NULL;
}

RegisterResult registry_register(const char *name) {
    if (!valid_name(name)) {
        return REGISTER_ERROR;
    }
    pthread_mutex_lock(&lock);
    RegisterResult result = REGISTER_OK;
    if (find_user(name) != NULL) {
        result = REGISTER_TAKEN;
    } else {
        User *grown = realloc(users, (user_count + 1) * sizeof(User));
        if (grown == NULL) {
            result = REGISTER_ERROR;
        } else {
            users = grown;
            users[user_count] = (User){0};
            copy_text(users[user_count].name, name, FIELD_CAPACITY);
            user_count++;
        }
    }
    pthread_mutex_unlock(&lock);
    return result;
}

UnregisterResult registry_unregister(const char *name) {
    if (!valid_name(name)) {
        return UNREGISTER_ERROR;
    }
    pthread_mutex_lock(&lock);
    UnregisterResult result = UNREGISTER_OK;
    User *user = find_user(name);
    if (user == NULL) {
        result = UNREGISTER_UNKNOWN;
    } else if (user->connected) {
        result = UNREGISTER_ERROR;
    } else {
        free(user->files);
        *user = users[--user_count];
    }
    pthread_mutex_unlock(&lock);
    return result;
}

ConnectResult registry_connect(const char *name, const char *address, int port) {
    if (!valid_name(name) || address == NULL || port <= 0 || port > 65535) {
        return CONNECT_ERROR;
    }
    pthread_mutex_lock(&lock);
    ConnectResult result = CONNECT_OK;
    User *user = find_user(name);
    if (user == NULL) {
        result = CONNECT_UNKNOWN;
    } else if (user->connected) {
        result = CONNECT_ALREADY_CONNECTED;
    } else {
        copy_text(user->address, address, ADDRESS_CAPACITY);
        user->port = port;
        user->connected = true;
    }
    pthread_mutex_unlock(&lock);
    return result;
}

DisconnectResult registry_disconnect(const char *name) {
    if (!valid_name(name)) {
        return DISCONNECT_ERROR;
    }
    pthread_mutex_lock(&lock);
    DisconnectResult result = DISCONNECT_OK;
    User *user = find_user(name);
    if (user == NULL) {
        result = DISCONNECT_UNKNOWN;
    } else if (!user->connected) {
        result = DISCONNECT_NOT_CONNECTED;
    } else {
        user->connected = false;
    }
    pthread_mutex_unlock(&lock);
    return result;
}

PublishResult registry_publish(const char *name, const char *file, const char *description) {
    if (!valid_name(name) || !valid_name(file) || !valid_name(description)) {
        return PUBLISH_ERROR;
    }
    pthread_mutex_lock(&lock);
    PublishResult result = PUBLISH_OK;
    User *user = find_user(name);
    if (user == NULL) {
        result = PUBLISH_UNKNOWN;
    } else if (!user->connected) {
        result = PUBLISH_NOT_CONNECTED;
    } else if (find_file(user, file) != NULL) {
        result = PUBLISH_DUPLICATE;
    } else {
        SharedFile *grown = realloc(user->files, (user->file_count + 1) * sizeof(SharedFile));
        if (grown == NULL) {
            result = PUBLISH_ERROR;
        } else {
            user->files = grown;
            copy_text(user->files[user->file_count].name, file, FIELD_CAPACITY);
            copy_text(user->files[user->file_count].description, description, FIELD_CAPACITY);
            user->file_count++;
        }
    }
    pthread_mutex_unlock(&lock);
    return result;
}

DeleteResult registry_delete(const char *name, const char *file) {
    if (!valid_name(name) || !valid_name(file)) {
        return DELETE_ERROR;
    }
    pthread_mutex_lock(&lock);
    DeleteResult result = DELETE_OK;
    User *user = find_user(name);
    SharedFile *shared = user == NULL ? NULL : find_file(user, file);
    if (user == NULL) {
        result = DELETE_UNKNOWN;
    } else if (!user->connected) {
        result = DELETE_NOT_CONNECTED;
    } else if (shared == NULL) {
        result = DELETE_MISSING;
    } else {
        *shared = user->files[--user->file_count];
    }
    pthread_mutex_unlock(&lock);
    return result;
}

ListUsersResult registry_list_users(const char *name, PeerList *peers) {
    *peers = (PeerList){0};
    if (!valid_name(name)) {
        return LIST_USERS_ERROR;
    }
    pthread_mutex_lock(&lock);
    ListUsersResult result = LIST_USERS_OK;
    User *user = find_user(name);
    if (user == NULL) {
        result = LIST_USERS_UNKNOWN;
    } else if (!user->connected) {
        result = LIST_USERS_NOT_CONNECTED;
    } else {
        peers->items = calloc(user_count, sizeof(Peer));
        if (peers->items == NULL) {
            result = LIST_USERS_ERROR;
        }
        for (size_t i = 0; result == LIST_USERS_OK && i < user_count; i++) {
            if (!users[i].connected) {
                continue;
            }
            Peer *peer = &peers->items[peers->count++];
            copy_text(peer->name, users[i].name, FIELD_CAPACITY);
            copy_text(peer->address, users[i].address, ADDRESS_CAPACITY);
            peer->port = users[i].port;
        }
    }
    pthread_mutex_unlock(&lock);
    return result;
}

ListContentResult registry_list_content(const char *name, const char *target, FileList *files) {
    *files = (FileList){0};
    if (!valid_name(name) || !valid_name(target)) {
        return LIST_CONTENT_ERROR;
    }
    pthread_mutex_lock(&lock);
    ListContentResult result = LIST_CONTENT_OK;
    User *user = find_user(name);
    User *owner = find_user(target);
    if (user == NULL) {
        result = LIST_CONTENT_UNKNOWN;
    } else if (!user->connected) {
        result = LIST_CONTENT_NOT_CONNECTED;
    } else if (owner == NULL) {
        result = LIST_CONTENT_TARGET_UNKNOWN;
    } else if (owner->file_count > 0) {
        files->names = calloc(owner->file_count, FIELD_CAPACITY);
        if (files->names == NULL) {
            result = LIST_CONTENT_ERROR;
        } else {
            for (size_t i = 0; i < owner->file_count; i++) {
                copy_text(files->names[i], owner->files[i].name, FIELD_CAPACITY);
            }
            files->count = owner->file_count;
        }
    }
    pthread_mutex_unlock(&lock);
    return result;
}

void registry_clear(void) {
    pthread_mutex_lock(&lock);
    for (size_t i = 0; i < user_count; i++) {
        free(users[i].files);
    }
    free(users);
    users = NULL;
    user_count = 0;
    pthread_mutex_unlock(&lock);
}

void peer_list_free(PeerList *peers) {
    free(peers->items);
    *peers = (PeerList){0};
}

void file_list_free(FileList *files) {
    free(files->names);
    *files = (FileList){0};
}
