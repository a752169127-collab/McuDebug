/*
 * Minimal RTT Normal source for MCU Debug Assistant V0.3 / SEGGER J-Scope.
 * Requires SEGGER_RTT.c / SEGGER_RTT.h in the target project.
 *
 * Channel name JScope_t4f4f4 means each packet is exactly:
 *   uint32_t timestamp_us;
 *   float    value1;
 *   float    value2;
 *
 * Call DebugScope_RTT_Init() once, then DebugScope_RTT_Push() at the desired
 * target-side sample rate. timestamp_us must be a monotonically increasing
 * 32-bit microsecond tick; wraparound is handled by the host decoder.
 */

#include <stdint.h>
#include <string.h>
#include "SEGGER_RTT.h"

#define DEBUG_SCOPE_RTT_UP_INDEX   1u
#define DEBUG_SCOPE_RTT_BUFFER_SIZE 4096u

static unsigned char s_DebugScopeRttBuffer[DEBUG_SCOPE_RTT_BUFFER_SIZE];

static void _PutU32LE(unsigned char *p, uint32_t v) {
    p[0] = (unsigned char)(v >> 0);
    p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16);
    p[3] = (unsigned char)(v >> 24);
}

static void _PutF32LE(unsigned char *p, float v) {
    uint32_t bits;
    memcpy(&bits, &v, sizeof(bits));
    _PutU32LE(p, bits);
}

void DebugScope_RTT_Init(void) {
    SEGGER_RTT_ConfigUpBuffer(
        DEBUG_SCOPE_RTT_UP_INDEX,
        "JScope_t4f4f4",
        s_DebugScopeRttBuffer,
        sizeof(s_DebugScopeRttBuffer),
        SEGGER_RTT_MODE_NO_BLOCK_SKIP
    );
}

void DebugScope_RTT_Push(uint32_t timestamp_us, float value1, float value2) {
    unsigned char packet[12];
    _PutU32LE(&packet[0], timestamp_us);
    _PutF32LE(&packet[4], value1);
    _PutF32LE(&packet[8], value2);
    (void)SEGGER_RTT_Write(DEBUG_SCOPE_RTT_UP_INDEX, packet, sizeof(packet));
}
