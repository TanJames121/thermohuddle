/*
 * ThermoHuddle bench test 04 — INMP441 I2S MEMS microphone
 * --------------------------------------------------------
 * Proves: I2S RX works at 16 kHz mono and audio levels are sane.
 *         Watch the RMS/peak bars: silence ~ <100, talking ~ 500-5000,
 *         clipping = 32767 (too close / too loud).
 *
 * Wiring:  INMP441 VDD -> 3.3V (!!), GND -> GND
 *          L/R  -> GND      (left slot = mono)
 *          SCK  -> GPIO 32  (BCLK)
 *          WS   -> GPIO 25  (LRCL)
 *          SD   -> GPIO 33  (DOUT)
 *
 * 16 kHz mono is the production rate for the MFCC distress pipeline
 * (th-audiod: 1 kHz high-pass, 13 MFCCs, 1-8 kHz band) - if this sketch
 * streams clean at 16 kHz on the ESP32, the mic and wiring are good.
 *
 * Core compatibility: works on arduino-esp32 core 2.x (driver/i2s.h)
 * and 3.x (ESP_I2S.h) - detected at compile time below.
 */

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  // -------- arduino-esp32 core 3.x --------
  #include <ESP_I2S.h>
  I2SClass i2s;
  const int I2S_SCK = 32, I2S_WS = 25, I2S_SD = 33;
#else
  // -------- arduino-esp32 core 2.x --------
  #include <driver/i2s.h>
  const int I2S_SCK = 32, I2S_WS = 25, I2S_SD = 33;
  #define I2S_STD_ONLY
#endif

const uint32_t SAMPLE_RATE = 16000;
const size_t   BUF_SAMPLES = 1024;     // 64 ms window

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== INMP441 I2S mic test (16 kHz mono) ===");

#if defined(I2S_STD_ONLY)
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,      // L/R tied to GND
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  Serial.println("core 2.x I2S driver installed");
#else
  i2s.setPins(I2S_SCK, I2S_WS, /*dout*/ -1, I2S_SD, /*mclk*/ -1);
  if (!i2s.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_32BIT,
                 I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT)) {
    Serial.println("I2S begin FAILED - check wiring");
    while (true) delay(1000);
  }
  Serial.println("core 3.x I2S started");
#endif
}

void loop() {
  int32_t buf[BUF_SAMPLES];
  size_t got = 0;

#if defined(I2S_STD_ONLY)
  i2s_read(I2S_NUM_0, buf, sizeof(buf), &got, portMAX_DELAY);
  got /= sizeof(int32_t);
#else
  got = i2s.readBytes((char*)buf, sizeof(buf)) / sizeof(int32_t);
#endif
  if (got == 0) { Serial.println("no data"); return; }

  // int24-in-int32: shift arithmetic >>8, then measure
  int64_t sumSq = 0;
  int32_t peak = 0;
  for (size_t i = 0; i < got; i++) {
    int32_t s = buf[i] >> 8;
    sumSq += (int64_t)s * s;
    int32_t a = s < 0 ? -s : s;
    if (a > peak) peak = a;
  }
  float rms = sqrtf((float)(sumSq / got));

  Serial.printf("RMS %8.0f | peak %7ld | ", rms, (long)peak);
  int bars = (int)(rms / 200.0f); if (bars > 50) bars = 50;
  for (int i = 0; i < bars; i++) Serial.print('#');
  Serial.println(rms > 32000 ? "  CLIPPING?" : "");

  delay(100);
}
