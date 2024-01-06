#pragma once

#include "esphome/core/component.h"

#include <memory>

namespace esphome {
namespace power_management {

enum PmLockType {

  CPU_FREQ_MAX = 0,
  APB_FREQ_MAX = 1,
  NO_LIGHT_SLEEP = 2,

};

class PMLock {
 public:
  PMLock(){};
  PMLock(const std::string &name, PmLockType lock){};
  ~PMLock(){};
};

class PowerManagement : public Component {
 public:
#ifdef USE_ESP32
  virtual void set_freq(uint16_t min_freq_mhz, uint16_t max_freq_mhz) = 0;
  virtual void set_tickless(bool tickless) = 0;
#endif
#ifdef USE_ESP8266
  virtual void set_loop_interval(uint16_t min_loop_interval_ms, uint16_t max_loop_interval_ms) = 0;
  virtual uint16_t get_min_loop_interval() const  = 0; 
  virtual uint16_t get_max_loop_interval() const  = 0;
#endif

  virtual std::unique_ptr<power_management::PMLock> get_lock(std::string name, PmLockType lock) = 0;
};

extern PowerManagement *global_pm;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

}  // namespace power_management
}  // namespace esphome
