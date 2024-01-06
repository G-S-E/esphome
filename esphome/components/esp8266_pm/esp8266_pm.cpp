#include "esphome/core/hal.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"

#include "esp8266_pm.h"

#include <sstream>

namespace esphome {
namespace esp8266_pm {

static const char *const TAG = "ESP8266PowerManagement";

void dump_locks() { 
}

void ESP8266PowerManagement::setup() { 
  ESP_LOGI(TAG, "ESP8266_PM Support Enabled");
  ESP_LOGI(TAG, "Setting Minimum loop interval to %dms, Maximum to %dms", min_loop_interval_, max_loop_interval_); 
  this->setup_done_ = true;  
  App.set_loop_interval(this->min_loop_interval_);
  power_management::global_pm = this; 
}

void ESP8266PowerManagement::loop() {
  // Disable the startup lock once we have looped once
  if (this->setup_done_) {
    App.set_loop_interval(this->max_loop_interval_);
    this->setup_done_ = false;
  }
}

void ESP8266PowerManagement::dump_config() { 
  ESP_LOGCONFIG(TAG, "PM Support Enabled");
  ESP_LOGCONFIG(TAG, "Setting Minimum loop interval to %dms, Maximum to %dms", min_loop_interval_, max_loop_interval_);
#if ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_VERBOSE
  dump_locks();
#endif 
}

void ESP8266PowerManagement::set_loop_interval(uint16_t min_loop_interval, uint16_t max_loop_interval) {
  this->min_loop_interval_ = min_loop_interval;
  this->max_loop_interval_ = max_loop_interval;
}

std::unique_ptr<power_management::PMLock> ESP8266PowerManagement::get_lock(std::string name,
                                                                         power_management::PmLockType lock) {
  return make_unique<ESPPMLock>(name, lock);
}

ESPPMLock::ESPPMLock(const std::string &name, power_management::PmLockType lock) {
  name_ = name;
  lock_ = lock; 
  App.set_loop_interval(power_management::global_pm->get_min_loop_interval());
  ESP_LOGD(TAG, "%s PM Lock Aquired", name_.c_str()); 
}

ESPPMLock::~ESPPMLock() { 
  App.set_loop_interval(power_management::global_pm->get_max_loop_interval());
  ESP_LOGD(TAG, "%s PM Lock Released", name_.c_str());
#if ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_VERBOSE
  dump_locks();
#endif 
}

}  // namespace esp8266_pm
}  // namespace esphome