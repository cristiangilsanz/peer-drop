#include "audit.h"

#include <stdio.h>
#include <stdlib.h>

#include "logger.h"

void audit_operation(const char *user, const char *operation, const char *file, const char *timestamp) {
    const char *host = getenv("PEER_DROP_LOGGER_HOST");
    if (host == NULL || host[0] == '\0') {
        return;
    }
    CLIENT *client = clnt_create(host, LOGGER, LOGGER_VERSION, "tcp");
    if (client == NULL) {
        clnt_pcreateerror(host);
        return;
    }
    struct timeval timeout = {.tv_sec = 2, .tv_usec = 0};
    clnt_control(client, CLSET_TIMEOUT, (char *)&timeout);
    log_entry entry = {
        .username = (char *)user,
        .operation = (char *)operation,
        .filename = (char *)file,
        .timestamp = (char *)timestamp,
    };
    int result = 0;
    if (log_operation_1(entry, &result, client) != RPC_SUCCESS) {
        clnt_perror(client, "logger");
    }
    clnt_destroy(client);
}
