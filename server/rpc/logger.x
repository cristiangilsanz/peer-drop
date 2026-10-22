struct log_entry {
    string username<256>;
    string operation<256>;
    string filename<256>;
    string timestamp<256>;
};

program LOGGER {
    version LOGGER_VERSION {
        int log_operation(log_entry entry) = 1;
    } = 1;
} = 0x20000042;
