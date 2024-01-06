import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID 
from esphome.core import CORE

CONF_MAX_LOOP_INTERVAL_MS = "max_loop_interval_ms"
CONF_MIN_LOOP_INTERVAL_MS = "min_loop_interval_ms" 

DEPENDENCIES = ["esp8266"]

pm_ns = cg.esphome_ns.namespace("esp8266_pm")
PM = pm_ns.class_("ESP8266PowerManagement", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(PM),
        cv.Optional(CONF_MAX_LOOP_INTERVAL_MS, default=200): cv.uint16_t,
        cv.Optional(CONF_MIN_LOOP_INTERVAL_MS, default=16): cv.uint16_t, 
    }
).extend(cv.COMPONENT_SCHEMA)


def to_code(config):
    cg.add_define("USE_PM")
    var = cg.new_Pvariable(config[CONF_ID])
    cg.add(var.set_loop_interval(config[CONF_MIN_LOOP_INTERVAL_MS], config[CONF_MAX_LOOP_INTERVAL_MS])) 
    yield cg.register_component(var, config)
    cg.add_global(pm_ns.using)

