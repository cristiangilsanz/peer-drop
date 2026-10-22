CC ?= gcc
CFLAGS ?= -O2 -g
STRICT = -std=c11 -D_DEFAULT_SOURCE -Wall -Wextra -Werror -pthread
RPC_CFLAGS := $(shell pkg-config --cflags libtirpc)
RPC_LIBS := $(shell pkg-config --libs libtirpc)

BUILD = build
GENERATED = $(BUILD)/generated
RPC = server/rpc/logger.x
INCLUDES = -Iserver/src -I$(GENERATED)

SERVER_SOURCES = $(wildcard server/src/*.c)
SERVER_OBJECTS = $(SERVER_SOURCES:server/src/%.c=$(BUILD)/server/%.o)
CORE_OBJECTS = $(BUILD)/server/registry.o $(BUILD)/server/protocol.o

all: $(BUILD)/peer-drop-server $(BUILD)/peer-drop-logger

$(GENERATED)/logger.x: $(RPC)
	@mkdir -p $(GENERATED)
	cp $< $@

$(GENERATED)/logger.h: $(GENERATED)/logger.x
	cd $(GENERATED) && rpcgen -NM -h -o logger.h logger.x

$(GENERATED)/logger_xdr.c: $(GENERATED)/logger.h
	cd $(GENERATED) && rpcgen -NM -c -o logger_xdr.c logger.x

$(GENERATED)/logger_clnt.c: $(GENERATED)/logger.h
	cd $(GENERATED) && rpcgen -NM -l -o logger_clnt.c logger.x

$(GENERATED)/logger_svc.c: $(GENERATED)/logger.h
	cd $(GENERATED) && rpcgen -NM -s tcp -o logger_svc.c logger.x

$(BUILD)/server/%.o: server/src/%.c $(GENERATED)/logger.h $(wildcard server/src/*.h)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(STRICT) $(INCLUDES) $(RPC_CFLAGS) -c -o $@ $<

$(BUILD)/logger/logger.o: server/logger/logger.c $(GENERATED)/logger.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(STRICT) $(INCLUDES) $(RPC_CFLAGS) -c -o $@ $<

$(BUILD)/generated/%.o: $(GENERATED)/%.c
	$(CC) $(CFLAGS) -pthread $(INCLUDES) $(RPC_CFLAGS) -w -c -o $@ $<

$(BUILD)/peer-drop-server: $(SERVER_OBJECTS) $(GENERATED)/logger_clnt.o $(GENERATED)/logger_xdr.o
	$(CC) $(CFLAGS) -pthread -o $@ $^ $(RPC_LIBS)

$(BUILD)/peer-drop-logger: $(BUILD)/logger/logger.o $(GENERATED)/logger_svc.o $(GENERATED)/logger_xdr.o
	$(CC) $(CFLAGS) -pthread -o $@ $^ $(RPC_LIBS)

$(BUILD)/registry-test: server/tests/registry_test.c $(CORE_OBJECTS)
	$(CC) $(CFLAGS) $(STRICT) $(INCLUDES) -o $@ $^

test: $(BUILD)/registry-test
	./$(BUILD)/registry-test

clean:
	rm -rf $(BUILD)

.PHONY: all test clean
