#pragma once

#include "esphome/core/component.h"
#include "esphome/components/power_management/power_management.h"

#include <memory> 
 
namespace esphome {
namespace esp8266_pm {

class ESPPMLock : public power_management::PMLock {
 public:
  ESPPMLock(const std::string &name, power_management::PmLockType lock);
  ~ESPPMLock();

 private:
  std::string name_;
  power_management::PmLockType lock_; 
};

class ESP8266PowerManagement : public power_management::PowerManagement {
 public:
  void setup() override;
  void set_loop_interval(uint16_t min_loop_interval, uint16_t max_loop_interval) override;
  uint16_t get_min_loop_interval() const override { return this->min_loop_interval_; } 
  uint16_t get_max_loop_interval() const override { return this->max_loop_interval_; } 
  float get_setup_priority() const override { return setup_priority::BUS; } 
  void loop() override;
  void dump_config() override;

  std::unique_ptr<power_management::PMLock> get_lock(std::string name, power_management::PmLockType lock) override;

 private:
  uint16_t min_loop_interval_ = 16;
  uint16_t max_loop_interval_ = 200; 
  bool setup_done_ = false;
};

}  // namespace esp8266_pm
}  // namespace esphome 
