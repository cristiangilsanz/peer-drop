#include <arpa/inet.h>
#include <errno.h>
#include <netdb.h>
#include <netinet/in.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "handlers.h"
#include "registry.h"

typedef struct {
    int socket;
    char address[ADDRESS_CAPACITY];
} Connection;

static volatile sig_atomic_t stopping;

static void request_stop(int signal_number) {
    (void)signal_number;
    stopping = 1;
}

static void *serve(void *argument) {
    Connection *connection = argument;
    handle_client(connection->socket, connection->address);
    close(connection->socket);
    free(connection);
    return NULL;
}

static int parse_port(int argc, char *argv[]) {
    int option;
    long port = -1;
    while ((option = getopt(argc, argv, "p:")) != -1) {
        if (option != 'p') {
            return -1;
        }
        char *end = NULL;
        port = strtol(optarg, &end, 10);
        if (*end != '\0') {
            return -1;
        }
    }
    return port > 0 && port <= 65535 ? (int)port : -1;
}

static void local_address(char address[ADDRESS_CAPACITY]) {
    char host[256];
    struct addrinfo hints = {.ai_family = AF_INET, .ai_socktype = SOCK_STREAM};
    struct addrinfo *found = NULL;
    snprintf(address, ADDRESS_CAPACITY, "0.0.0.0");
    if (gethostname(host, sizeof(host)) != 0 || getaddrinfo(host, NULL, &hints, &found) != 0) {
        return;
    }
    struct sockaddr_in *ipv4 = (struct sockaddr_in *)found->ai_addr;
    inet_ntop(AF_INET, &ipv4->sin_addr, address, ADDRESS_CAPACITY);
    freeaddrinfo(found);
}

static int open_listener(int port) {
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) {
        return -1;
    }
    int reuse = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    struct sockaddr_in address = {
        .sin_family = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_ANY),
        .sin_port = htons((uint16_t)port),
    };
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) < 0 || listen(listener, SOMAXCONN) < 0) {
        close(listener);
        return -1;
    }
    return listener;
}

static void install_signal_handlers(void) {
    struct sigaction action = {.sa_handler = request_stop};
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, NULL);
    sigaction(SIGTERM, &action, NULL);
    signal(SIGPIPE, SIG_IGN);
}

static void spawn_worker(Connection *connection) {
    sigset_t blocked;
    sigset_t previous;
    sigemptyset(&blocked);
    sigaddset(&blocked, SIGINT);
    sigaddset(&blocked, SIGTERM);
    pthread_sigmask(SIG_BLOCK, &blocked, &previous);
    pthread_t thread;
    if (pthread_create(&thread, NULL, serve, connection) == 0) {
        pthread_detach(thread);
    } else {
        close(connection->socket);
        free(connection);
    }
    pthread_sigmask(SIG_SETMASK, &previous, NULL);
}

int main(int argc, char *argv[]) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    int port = parse_port(argc, argv);
    if (port < 0) {
        fprintf(stderr, "Usage: %s -p <port>\n", argv[0]);
        return EXIT_FAILURE;
    }
    install_signal_handlers();
    int listener = open_listener(port);
    if (listener < 0) {
        perror("Cannot listen on the port");
        return EXIT_FAILURE;
    }
    char address[ADDRESS_CAPACITY];
    local_address(address);
    printf("init server %s:%d\n", address, port);

    while (!stopping) {
        struct sockaddr_in client = {0};
        socklen_t size = sizeof(client);
        int socket = accept(listener, (struct sockaddr *)&client, &size);
        if (socket < 0) {
            if (errno != EINTR) {
                perror("Cannot accept a connection");
            }
            continue;
        }
        Connection *connection = malloc(sizeof(Connection));
        if (connection == NULL) {
            close(socket);
            continue;
        }
        connection->socket = socket;
        inet_ntop(AF_INET, &client.sin_addr, connection->address, ADDRESS_CAPACITY);
        spawn_worker(connection);
    }

    close(listener);
    registry_clear();
    printf("server stopped\n");
    return EXIT_SUCCESS;
}
