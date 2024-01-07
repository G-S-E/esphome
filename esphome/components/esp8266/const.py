import esphome.codegen as cg

KEY_ESP8266 = "esp8266"
KEY_BOARD = "board"
KEY_VARIANT = "variant"
KEY_PIN_INITIAL_STATES = "pin_initial_states"
KEY_SDKCONFIG_OPTIONS = "sdkconfig_options"
KEY_COMPONENTS = "components"
KEY_REPO = "repo"
KEY_REF = "ref"
KEY_REFRESH = "refresh"
KEY_SUBMODULES = "submodules"
CONF_RESTORE_FROM_FLASH = "restore_from_flash"
CONF_EARLY_PIN_INIT = "early_pin_init"
KEY_FLASH_SIZE = "flash_size"
KEY_PATH = "path"
KEY_EXTRA_BUILD_FILES = "extra_build_files"

# esp8266 namespace is already defined by arduino, manually prefix esphome
esp8266_ns = cg.global_ns.namespace("esphome").namespace("esp8266")
