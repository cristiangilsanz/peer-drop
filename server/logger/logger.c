#include <pthread.h>
#include <stdio.h>

#include "logger.h"

static pthread_mutex_t output_lock = PTHREAD_MUTEX_INITIALIZER;

bool_t log_operation_1_svc(log_entry entry, int *result, struct svc_req *request) {
    (void)request;
    pthread_mutex_lock(&output_lock);
    if (entry.filename[0] != '\0') {
        printf("%s %s %s %s\n", entry.username, entry.operation, entry.filename, entry.timestamp);
    } else {
        printf("%s %s %s\n", entry.username, entry.operation, entry.timestamp);
    }
    fflush(stdout);
    pthread_mutex_unlock(&output_lock);
    *result = 0;
    return TRUE;
}

int logger_1_freeresult(SVCXPRT *transport, xdrproc_t free_result, caddr_t result) {
    (void)transport;
    xdr_free(free_result, result);
    return TRUE;
}
