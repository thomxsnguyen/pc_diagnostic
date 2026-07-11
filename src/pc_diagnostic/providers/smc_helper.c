#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>

// Forward declarations for HID event system client private APIs
typedef struct __IOHIDEvent *IOHIDEventRef;
typedef struct __IOHIDServiceClient *IOHIDServiceClientRef;
typedef struct __IOHIDEventSystemClient *IOHIDEventSystemClientRef;

extern IOHIDEventSystemClientRef IOHIDEventSystemClientCreate(CFAllocatorRef allocator);
extern CFArrayRef IOHIDEventSystemClientCopyServices(IOHIDEventSystemClientRef client);
extern CFTypeRef IOHIDServiceClientCopyProperty(IOHIDServiceClientRef service, CFStringRef property);
extern IOHIDEventRef IOHIDServiceClientCopyEvent(IOHIDServiceClientRef service, int64_t eventType, uint32_t options, uint32_t flags);
extern double IOHIDEventGetFloatValue(IOHIDEventRef event, int32_t field);

#define kIOHIDEventTypeTemperature 15
#define kIOHIDEventFieldTemperatureValue 983040 // (15 << 16)

// Traditional Intel SMC struct Definitions
#define KERNEL_INDEX_SMC 2
#define SMC_CMD_READ_BYTES 5
#define SMC_CMD_READ_KEYINFO 9

typedef struct {
    char major;
    char minor;
    char build;
    char reserved[1];
} SMCVersion;

typedef struct {
    uint16_t version;
    uint16_t length;
    uint32_t cpuOS;
    uint32_t status;
} SMCPLimitData;

typedef struct {
    uint32_t key;
    uint32_t dataSize;
    uint32_t dataType;
    uint8_t bytes[32];
} SMCKeyInfoData;

typedef struct {
    uint32_t key;
    uint32_t dataSize;
    uint32_t dataType;
    uint8_t bytes[32];
} SMCVal;

typedef struct {
    uint32_t key;
    uint8_t vers;
    uint8_t pLimit;
    uint8_t pad[2];
    SMCPLimitData pLimitData;
    SMCKeyInfoData keyInfo;
    SMCVal val;
    uint8_t result;
} SMCParamStruct;

// Convert 4-char string key to uint32_t
uint32_t ultra_key(const char *str) {
    uint32_t val = 0;
    for (int i = 0; i < 4; i++) {
        if (str[i] == '\0') break;
        val = (val << 8) + (uint8_t)str[i];
    }
    return val;
}

// Convert 4-char string type to uint32_t
uint32_t ultra_type(const char *str) {
    return ultra_key(str);
}

// Convert float to SMC fpe2 format (16-bit unsigned, integer 14 bits, fraction 2 bits)
float get_fpe2(uint8_t *bytes) {
    return (float)((bytes[0] << 6) + (bytes[1] >> 2));
}

// Convert float to SMC sp78 format (16-bit signed, integer 8 bits, fraction 8 bits)
float get_sp78(uint8_t *bytes) {
    return (float)(int8_t)bytes[0] + (float)bytes[1] / 256.0;
}

// Read an SMC key from connection
kern_return_t smc_read_key(io_connect_t conn, const char *key, SMCVal *val) {
    SMCParamStruct input;
    SMCParamStruct output;
    memset(&input, 0, sizeof(SMCParamStruct));
    memset(&output, 0, sizeof(SMCParamStruct));

    input.key = ultra_key(key);
    input.result = SMC_CMD_READ_KEYINFO;

    size_t out_size = sizeof(SMCParamStruct);
    kern_return_t result = IOConnectCallStructMethod(conn, KERNEL_INDEX_SMC, &input, sizeof(SMCParamStruct), &output, &out_size);
    if (result != kIOReturnSuccess) return result;

    uint32_t size = output.keyInfo.dataSize;
    uint32_t type = output.keyInfo.dataType;

    memset(&input, 0, sizeof(SMCParamStruct));
    input.key = ultra_key(key);
    input.val.dataSize = size;
    input.result = SMC_CMD_READ_BYTES;

    result = IOConnectCallStructMethod(conn, KERNEL_INDEX_SMC, &input, sizeof(SMCParamStruct), &output, &out_size);
    if (result != kIOReturnSuccess) return result;

    if (output.result != 0) return kIOReturnError;

    val->key = input.key;
    val->dataSize = size;
    val->dataType = type;
    memcpy(val->bytes, output.val.bytes, sizeof(val->bytes));
    return kIOReturnSuccess;
}

int main() {
    int first = 1;
    printf("[");

    // 1. Query IOHIDEventSystem thermal sensors (Primary for Apple Silicon)
    IOHIDEventSystemClientRef client = IOHIDEventSystemClientCreate(kCFAllocatorDefault);
    if (client) {
        CFArrayRef services = IOHIDEventSystemClientCopyServices(client);
        if (services) {
            CFIndex count = CFArrayGetCount(services);
            for (CFIndex i = 0; i < count; i++) {
                IOHIDServiceClientRef service = (IOHIDServiceClientRef)CFArrayGetValueAtIndex(services, i);
                if (!service) continue;

                CFStringRef product = (CFStringRef)IOHIDServiceClientCopyProperty(service, CFSTR("Product"));
                if (!product) continue;

                char name[128];
                if (CFStringGetCString(product, name, sizeof(name), kCFStringEncodingUTF8)) {
                    IOHIDEventRef event = IOHIDServiceClientCopyEvent(service, kIOHIDEventTypeTemperature, 0, 0);
                    if (event) {
                        double temp = IOHIDEventGetFloatValue(event, kIOHIDEventFieldTemperatureValue);
                        // Sensible range for live core/proximity sensors
                        if (temp > 0.0 && temp < 150.0) {
                            if (!first) printf(",");
                            first = 0;
                            printf("{\"sensor\":\"%s\",\"type\":\"Temperature\",\"value\":%.2f}", name, temp);
                        }
                        CFRelease(event);
                    }
                }
                CFRelease(product);
            }
            CFRelease(services);
        }
        CFRelease(client);
    }

    // 2. Query AppleSMC (Primary for Fans and fallback CPU temp on Intel)
    io_connect_t conn = 0;
    io_service_t service = IOServiceGetMatchingService(0, IOServiceMatching("AppleSMC"));
    if (service) {
        kern_return_t res = IOServiceOpen(service, mach_task_self(), 0, &conn);
        if (res == kIOReturnSuccess) {
            SMCVal val;
            
            // Read CPU Temperature if HID didn't return any
            if (first) {
                if (smc_read_key(conn, "TC0D", &val) == kIOReturnSuccess) {
                    float temp = get_sp78(val.bytes);
                    if (temp > 0.0 && temp < 150.0) {
                        if (!first) printf(",");
                        first = 0;
                        printf("{\"sensor\":\"CPU Die Temperature\",\"type\":\"Temperature\",\"value\":%.2f}", temp);
                    }
                }
            }

            // Read Fan 0 Actual Speed
            if (smc_read_key(conn, "F0Ac", &val) == kIOReturnSuccess) {
                float rpm = get_fpe2(val.bytes);
                if (rpm >= 0.0 && rpm < 10000.0) {
                    if (!first) printf(",");
                    first = 0;
                    printf("{\"sensor\":\"Fan 0 Speed\",\"type\":\"Fan\",\"value\":%.2f}", rpm);
                }
            }

            // Read Fan 1 Actual Speed (if present)
            if (smc_read_key(conn, "F1Ac", &val) == kIOReturnSuccess) {
                float rpm = get_fpe2(val.bytes);
                if (rpm >= 0.0 && rpm < 10000.0) {
                    if (!first) printf(",");
                    first = 0;
                    printf("{\"sensor\":\"Fan 1 Speed\",\"type\":\"Fan\",\"value\":%.2f}", rpm);
                }
            }

            IOServiceClose(conn);
        }
        IOObjectRelease(service);
    }

    printf("]\n");
    return 0;
}
