#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "registry.h"

static int failures;

#define CHECK(condition)                                                    \
    do {                                                                    \
        if (!(condition)) {                                                 \
            fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
            failures++;                                                     \
        }                                                                   \
    } while (0)

static void test_register_and_unregister(void) {
    CHECK(registry_register("alice") == REGISTER_OK);
    CHECK(registry_register("alice") == REGISTER_TAKEN);
    CHECK(registry_register("") == REGISTER_ERROR);
    CHECK(registry_unregister("bob") == UNREGISTER_UNKNOWN);
    CHECK(registry_unregister("alice") == UNREGISTER_OK);
    CHECK(registry_register("alice") == REGISTER_OK);
    registry_clear();
}

static void test_names_are_plain_text(void) {
    CHECK(registry_register("../../escape") == REGISTER_OK);
    CHECK(registry_register("../../escape") == REGISTER_TAKEN);
    registry_clear();
}

static void test_connection_rules(void) {
    registry_register("alice");
    CHECK(registry_connect("bob", "127.0.0.1", 9000) == CONNECT_UNKNOWN);
    CHECK(registry_connect("alice", "127.0.0.1", 0) == CONNECT_ERROR);
    CHECK(registry_connect("alice", "127.0.0.1", 9000) == CONNECT_OK);
    CHECK(registry_connect("alice", "127.0.0.1", 9000) == CONNECT_ALREADY_CONNECTED);
    CHECK(registry_unregister("alice") == UNREGISTER_ERROR);
    CHECK(registry_disconnect("alice") == DISCONNECT_OK);
    CHECK(registry_disconnect("alice") == DISCONNECT_NOT_CONNECTED);
    CHECK(registry_disconnect("carol") == DISCONNECT_UNKNOWN);
    registry_clear();
}

static void test_publish_and_delete(void) {
    registry_register("alice");
    CHECK(registry_publish("alice", "notes.txt", "my notes") == PUBLISH_NOT_CONNECTED);
    registry_connect("alice", "127.0.0.1", 9000);
    CHECK(registry_publish("alice", "notes.txt", "my notes") == PUBLISH_OK);
    CHECK(registry_publish("alice", "notes.txt", "again") == PUBLISH_DUPLICATE);
    CHECK(registry_publish("alice", "empty.txt", "") == PUBLISH_ERROR);
    CHECK(registry_delete("alice", "missing.txt") == DELETE_MISSING);
    CHECK(registry_delete("alice", "notes.txt") == DELETE_OK);
    CHECK(registry_delete("alice", "notes.txt") == DELETE_MISSING);
    CHECK(registry_delete("bob", "notes.txt") == DELETE_UNKNOWN);
    registry_clear();
}

static void test_listings(void) {
    registry_register("alice");
    registry_register("bob");
    registry_register("carol");
    registry_connect("alice", "10.0.0.1", 9001);
    registry_connect("bob", "10.0.0.2", 9002);
    registry_publish("bob", "song.mp3", "a song");
    registry_publish("bob", "photo.png", "a photo");

    PeerList peers;
    CHECK(registry_list_users("carol", &peers) == LIST_USERS_NOT_CONNECTED);
    CHECK(registry_list_users("dave", &peers) == LIST_USERS_UNKNOWN);
    CHECK(registry_list_users("alice", &peers) == LIST_USERS_OK);
    CHECK(peers.count == 2);
    CHECK(strcmp(peers.items[1].name, "bob") == 0);
    CHECK(strcmp(peers.items[1].address, "10.0.0.2") == 0);
    CHECK(peers.items[1].port == 9002);
    peer_list_free(&peers);

    FileList files;
    CHECK(registry_list_content("alice", "dave", &files) == LIST_CONTENT_TARGET_UNKNOWN);
    CHECK(registry_list_content("carol", "bob", &files) == LIST_CONTENT_NOT_CONNECTED);
    CHECK(registry_list_content("alice", "bob", &files) == LIST_CONTENT_OK);
    CHECK(files.count == 2);
    CHECK(strcmp(files.names[0], "song.mp3") == 0);
    file_list_free(&files);
    CHECK(registry_list_content("alice", "carol", &files) == LIST_CONTENT_OK);
    CHECK(files.count == 0);
    file_list_free(&files);
    registry_clear();
}

static void test_long_names_are_rejected(void) {
    char name[FIELD_CAPACITY + 1];
    memset(name, 'a', FIELD_CAPACITY);
    name[FIELD_CAPACITY] = '\0';
    CHECK(registry_register(name) == REGISTER_ERROR);
    name[FIELD_CAPACITY - 1] = '\0';
    CHECK(registry_register(name) == REGISTER_OK);
    registry_clear();
}

int main(void) {
    test_register_and_unregister();
    test_names_are_plain_text();
    test_connection_rules();
    test_publish_and_delete();
    test_listings();
    test_long_names_are_rejected();
    if (failures > 0) {
        fprintf(stderr, "%d check(s) failed\n", failures);
        return EXIT_FAILURE;
    }
    printf("All registry tests passed\n");
    return EXIT_SUCCESS;
}
