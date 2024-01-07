from dataclasses import dataclass
import logging
import os

from typing import Union, Optional

import esphome.final_validate as fv
from esphome.const import (
    CONF_BOARD,
    CONF_BOARD_FLASH_MODE,
    CONF_COMPONENTS,
    CONF_ESPHOME,
    CONF_FRAMEWORK,
    CONF_NAME,
    CONF_PATH,
    CONF_PLATFORMIO_OPTIONS,
    CONF_REF,
    CONF_REFRESH,
    CONF_SOURCE,
    CONF_TYPE,
    CONF_URL,
    CONF_VERSION,
    KEY_CORE,
    KEY_FRAMEWORK_VERSION,
    KEY_NAME,
    KEY_TARGET_FRAMEWORK,
    KEY_TARGET_PLATFORM,
    PLATFORM_ESP8266,
    TYPE_GIT,
    TYPE_LOCAL,
)
from esphome.core import CORE, coroutine_with_priority, HexInt, TimePeriod
import esphome.config_validation as cv
import esphome.codegen as cg
from esphome.helpers import copy_file_if_changed

from .const import (
    CONF_RESTORE_FROM_FLASH,
    CONF_EARLY_PIN_INIT,
    KEY_BOARD,
    KEY_COMPONENTS,
    KEY_ESP8266,
    KEY_EXTRA_BUILD_FILES,
    KEY_FLASH_SIZE,
    KEY_PIN_INITIAL_STATES,
    KEY_PATH,
    KEY_REF,
    KEY_REFRESH,
    KEY_REPO,
    KEY_SDKCONFIG_OPTIONS,
    KEY_SUBMODULES,
    esp8266_ns,
)
from .boards import BOARDS, ESP8266_LD_SCRIPTS

from .gpio import PinInitialState, add_pin_initial_states_array


CODEOWNERS = ["@esphome/core"]
_LOGGER = logging.getLogger(__name__)
AUTO_LOAD = ["preferences"]


def get_download_types(storage_json):
    return [
        {
            "title": "Standard format",
            "description": "For flashing ESP8266.",
            "file": "firmware.bin",
            "download": f"{storage_json.name}.bin",
        },
    ]


def set_core_data(config):
    CORE.data[KEY_ESP8266] = {}
    CORE.data[KEY_CORE][KEY_TARGET_PLATFORM] = PLATFORM_ESP8266
    conf = config[CONF_FRAMEWORK]
    if conf[CONF_TYPE] == FRAMEWORK_ESP_IDF:
        CORE.data[KEY_CORE][KEY_TARGET_FRAMEWORK] = "esp-idf"
        CORE.data[KEY_ESP8266][KEY_SDKCONFIG_OPTIONS] = {}
        CORE.data[KEY_ESP8266][KEY_COMPONENTS] = {}
    elif conf[CONF_TYPE] == FRAMEWORK_ARDUINO:
        CORE.data[KEY_CORE][KEY_TARGET_FRAMEWORK] = "arduino"
    CORE.data[KEY_CORE][KEY_FRAMEWORK_VERSION] = cv.Version.parse(
        config[CONF_FRAMEWORK][CONF_VERSION]
    )
    CORE.data[KEY_ESP8266][KEY_BOARD] = config[CONF_BOARD]
    CORE.data[KEY_ESP8266][KEY_PIN_INITIAL_STATES] = [
        PinInitialState() for _ in range(16)
    ]
    CORE.data[KEY_ESP8266][KEY_BOARD] = config[CONF_BOARD]
    CORE.data[KEY_ESP8266][KEY_EXTRA_BUILD_FILES] = {}

    return config


@dataclass
class RawSdkconfigValue:
    """An sdkconfig value that won't be auto-formatted"""

    value: str


SdkconfigValueType = Union[bool, int, HexInt, str, RawSdkconfigValue]


def add_idf_sdkconfig_option(name: str, value: SdkconfigValueType):
    """Set an esp-idf sdkconfig value."""
    if not CORE.using_esp_idf:
        raise ValueError("Not an esp-idf project")
    CORE.data[KEY_ESP8266][KEY_SDKCONFIG_OPTIONS][name] = value


def add_idf_component(
    *,
    name: str,
    repo: str,
    ref: str = None,
    path: str = None,
    refresh: TimePeriod = None,
    components: Optional[list[str]] = None,
    submodules: Optional[list[str]] = None,
):
    """Add an esp-idf component to the project."""
    if not CORE.using_esp_idf:
        raise ValueError("Not an esp-idf project")
    if components is None:
        components = []
    if name not in CORE.data[KEY_ESP8266][KEY_COMPONENTS]:
        CORE.data[KEY_ESP8266][KEY_COMPONENTS][name] = {
            KEY_REPO: repo,
            KEY_REF: ref,
            KEY_PATH: path,
            KEY_REFRESH: refresh,
            KEY_COMPONENTS: components,
            KEY_SUBMODULES: submodules,
        }


def add_extra_script(stage: str, filename: str, path: str):
    """Add an extra script to the project."""
    key = f"{stage}:{filename}"
    if add_extra_build_file(filename, path):
        cg.add_platformio_option("extra_scripts", [key])


def add_extra_build_file(filename: str, path: str) -> bool:
    """Add an extra build file to the project."""
    if filename not in CORE.data[KEY_ESP8266][KEY_EXTRA_BUILD_FILES]:
        CORE.data[KEY_ESP8266][KEY_EXTRA_BUILD_FILES][filename] = {
            KEY_NAME: filename,
            KEY_PATH: path,
        }
        return True
    return False


def _format_framework_arduino_version(ver: cv.Version) -> str:
    # format the given arduino (https://github.com/esp8266/Arduino/releases) version to
    # a PIO platformio/framework-arduinoespressif8266 value
    # List of package versions: https://api.registry.platformio.org/v3/packages/platformio/tool/framework-arduinoespressif8266
    if ver <= cv.Version(2, 4, 1):
        return f"~1.{ver.major}{ver.minor:02d}{ver.patch:02d}.0"
    if ver <= cv.Version(2, 6, 2):
        return f"~2.{ver.major}{ver.minor:02d}{ver.patch:02d}.0"
    return f"~3.{ver.major}{ver.minor:02d}{ver.patch:02d}.0"


def _format_framework_espidf_version(ver: cv.Version) -> str:
    return f"~v{ver.major}.{ver.minor}"


# NOTE: Keep this in mind when updating the recommended version:
#  * New framework historically have had some regressions, especially for WiFi.
#    The new version needs to be thoroughly validated before changing the
#    recommended version as otherwise a bunch of devices could be bricked
#  * For all constants below, update platformio.ini (in this repo)
#    and platformio.ini/platformio-lint.ini in the esphome-docker-base repository

# The default/recommended arduino framework version
#  - https://github.com/esp8266/Arduino/releases
#  - https://api.registry.platformio.org/v3/packages/platformio/tool/framework-arduinoespressif8266
RECOMMENDED_ARDUINO_FRAMEWORK_VERSION = cv.Version(3, 0, 2)
# The platformio/espressif8266 version to use for arduino 2 framework versions
#  - https://github.com/platformio/platform-espressif8266/releases
#  - https://api.registry.platformio.org/v3/packages/platformio/platform/espressif8266
ARDUINO_2_PLATFORM_VERSION = cv.Version(2, 6, 3)
# for arduino 3 framework versions
ARDUINO_3_PLATFORM_VERSION = cv.Version(3, 2, 0)

RECOMMENDED_ESP_IDF_FRAMEWORK_VERSION = cv.Version(3, 4, 0)
ESP_IDF_PLATFORM_VERSION = cv.Version(4, 2, 1)


def _arduino_check_versions(value):
    value = value.copy()
    lookups = {
        "dev": (cv.Version(3, 0, 2), "https://github.com/esp8266/Arduino.git"),
        "latest": (cv.Version(3, 0, 2), None),
        "recommended": (RECOMMENDED_ARDUINO_FRAMEWORK_VERSION, None),
    }

    if value[CONF_VERSION] in lookups:
        if CONF_SOURCE in value:
            raise cv.Invalid(
                "Framework version needs to be explicitly specified when custom source is used."
            )

        version, source = lookups[value[CONF_VERSION]]
    else:
        version = cv.Version.parse(cv.version_number(value[CONF_VERSION]))
        source = value.get(CONF_SOURCE, None)

    value[CONF_VERSION] = str(version)
    value[CONF_SOURCE] = source or _format_framework_arduino_version(version)

    platform_version = value.get(CONF_PLATFORM_VERSION)
    if platform_version is None:
        if version >= cv.Version(3, 0, 0):
            platform_version = _parse_platform_version(str(ARDUINO_3_PLATFORM_VERSION))
        elif version >= cv.Version(2, 5, 0):
            platform_version = _parse_platform_version(str(ARDUINO_2_PLATFORM_VERSION))
        else:
            platform_version = _parse_platform_version(str(cv.Version(1, 8, 0)))
    value[CONF_PLATFORM_VERSION] = platform_version

    if version != RECOMMENDED_ARDUINO_FRAMEWORK_VERSION:
        _LOGGER.warning(
            "The selected Arduino framework version is not the recommended one. "
            "If there are connectivity or build issues please remove the manual version."
        )

    return value


def _esp_idf_check_versions(value):
    value = value.copy()
    lookups = {
        "dev": (
            cv.Version(3, 4, 0),
            "https://github.com/espressif/ESP8266_RTOS_SDK.git",
        ),
        "latest": (
            cv.Version(3, 4, 0),
            "https://github.com/espressif/ESP8266_RTOS_SDK.git",
        ),
        "recommended": (
            RECOMMENDED_ESP_IDF_FRAMEWORK_VERSION,
            "https://github.com/espressif/ESP8266_RTOS_SDK.git",
        ),
    }

    if value[CONF_VERSION] in lookups:
        if CONF_SOURCE in value:
            raise cv.Invalid(
                "Framework version needs to be explicitly specified when custom source is used."
            )

        version, source = lookups[value[CONF_VERSION]]
    else:
        version = cv.Version.parse(cv.version_number(value[CONF_VERSION]))
        source = value.get(CONF_SOURCE, None)

    value[CONF_VERSION] = str(version)
    value[CONF_SOURCE] = source or _format_framework_espidf_version(version)

    value[CONF_PLATFORM_VERSION] = value.get(
        CONF_PLATFORM_VERSION, _parse_platform_version(str(ESP_IDF_PLATFORM_VERSION))
    )

    if version != RECOMMENDED_ESP_IDF_FRAMEWORK_VERSION:
        _LOGGER.warning(
            "The selected ESP-IDF framework version is not the recommended one. "
            "If there are connectivity or build issues please remove the manual version."
        )

    return value


def _parse_platform_version(value):
    try:
        # if platform version is a valid version constraint, prefix the default package
        cv.platformio_version_constraint(value)
        return f"platformio/espressif8266@{value}"
    except cv.Invalid:
        _LOGGER.error(f"Unknown platform version: {value}")
        return value


def final_validate(config):
    if CONF_PLATFORMIO_OPTIONS not in fv.full_config.get()[CONF_ESPHOME]:
        return config

    pio_flash_size_key = "board_upload.flash_size"
    pio_partitions_key = "board_build.partitions"
    if (
        CONF_PARTITIONS in config
        and pio_partitions_key
        in fv.full_config.get()[CONF_ESPHOME][CONF_PLATFORMIO_OPTIONS]
    ):
        raise cv.Invalid(
            f"Do not specify '{pio_partitions_key}' in '{CONF_PLATFORMIO_OPTIONS}' with '{CONF_PARTITIONS}' in esp8266"
        )

    if (
        pio_flash_size_key
        in fv.full_config.get()[CONF_ESPHOME][CONF_PLATFORMIO_OPTIONS]
    ):
        raise cv.Invalid(
            f"Please specify {CONF_FLASH_SIZE} within esp8266 configuration only"
        )

    return config


CONF_PLATFORM_VERSION = "platform_version"

BUILD_FLASH_MODES = ["qio", "qout", "dio", "dout"]
ARDUINO_FRAMEWORK_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Optional(CONF_VERSION, default="recommended"): cv.string_strict,
            cv.Optional(CONF_SOURCE): cv.string_strict,
            cv.Optional(CONF_PLATFORM_VERSION): _parse_platform_version,
            cv.Optional(CONF_RESTORE_FROM_FLASH, default=False): cv.boolean,
            cv.Optional(CONF_EARLY_PIN_INIT, default=True): cv.boolean,
            cv.Optional(CONF_BOARD_FLASH_MODE, default="dout"): cv.one_of(
                *BUILD_FLASH_MODES, lower=True
            ),
        }
    ),
    _arduino_check_versions,
)

CONF_SDKCONFIG_OPTIONS = "sdkconfig_options"
ESP_IDF_FRAMEWORK_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Optional(CONF_VERSION, default="recommended"): cv.string_strict,
            cv.Optional(CONF_SOURCE): cv.string_strict,
            cv.Optional(CONF_PLATFORM_VERSION): _parse_platform_version,
            cv.Optional(CONF_SDKCONFIG_OPTIONS, default={}): {
                cv.string_strict: cv.string_strict
            },
            cv.Optional(CONF_COMPONENTS, default=[]): cv.ensure_list(
                cv.Schema(
                    {
                        cv.Required(CONF_NAME): cv.string_strict,
                        cv.Required(CONF_SOURCE): cv.SOURCE_SCHEMA,
                        cv.Optional(CONF_PATH): cv.string,
                        cv.Optional(CONF_REFRESH, default="1d"): cv.All(
                            cv.string, cv.source_refresh
                        ),
                    }
                )
            ),
        }
    ),
    _esp_idf_check_versions,
)


FRAMEWORK_ESP_IDF = "esp8266-rtos-sdk"
FRAMEWORK_ARDUINO = "arduino"
FRAMEWORK_SCHEMA = cv.typed_schema(
    {
        FRAMEWORK_ESP_IDF: ESP_IDF_FRAMEWORK_SCHEMA,
        FRAMEWORK_ARDUINO: ARDUINO_FRAMEWORK_SCHEMA,
    },
    lower=True,
    space="-",
    default_type=FRAMEWORK_ARDUINO,
)


FLASH_SIZES = [
    "2MB",
    "4MB",
    "8MB",
    "16MB",
]

CONF_FLASH_SIZE = "flash_size"
CONF_PARTITIONS = "partitions"
CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Required(CONF_BOARD): cv.string_strict,
            cv.Optional(CONF_FLASH_SIZE, default="4MB"): cv.one_of(
                *FLASH_SIZES, upper=True
            ),
            cv.Optional(CONF_PARTITIONS): cv.file_,
            cv.Optional(CONF_FRAMEWORK, default={}): FRAMEWORK_SCHEMA,
        }
    ),
    set_core_data,
)


FINAL_VALIDATE_SCHEMA = cv.Schema(final_validate)


@coroutine_with_priority(1000)
async def to_code(config):
    cg.add(esp8266_ns.setup_preferences())

    cg.add_platformio_option("board", config[CONF_BOARD])
    cg.add_platformio_option("board_upload.flash_size", config[CONF_FLASH_SIZE])
    cg.add_build_flag("-DUSE_ESP8266")
    cg.add_define("ESPHOME_BOARD", config[CONF_BOARD])
    cg.add_define("ESPHOME_VARIANT", "ESP8266")

    cg.add_platformio_option("lib_ldf_mode", "off")

    framework_ver: cv.Version = CORE.data[KEY_CORE][KEY_FRAMEWORK_VERSION]

    conf = config[CONF_FRAMEWORK]
    cg.add_platformio_option("platform", conf[CONF_PLATFORM_VERSION])

    add_extra_script(
        "post",
        "post_build.py",
        os.path.join(os.path.dirname(__file__), "post_build.py.script"),
    )

    if conf[CONF_TYPE] == FRAMEWORK_ESP_IDF:
        cg.add_platformio_option("framework", "esp8266-rtos-sdk")
        cg.add_build_flag("-DUSE_ESP_IDF")
        cg.add_build_flag("-DUSE_ESP8266_FRAMEWORK_ESP_IDF")
        cg.add_build_flag("-Wno-nonnull-compare")
        cg.add_platformio_option(
            "platform_packages",
            [f"espressif/framework-esp8266-rtos-sdk@{conf[CONF_SOURCE]}"],
        )
        # platformio/toolchain-esp32ulp does not support linux_aarch64 yet and has not been updated for over 2 years
        # This is espressif's own published version which is more up to date.
        cg.add_platformio_option(
            "platform_packages", ["platformio/toolchain-xtensa@^2.0.0"]
        )
        add_idf_sdkconfig_option("CONFIG_PARTITION_TABLE_SINGLE_APP", False)
        add_idf_sdkconfig_option("CONFIG_PARTITION_TABLE_CUSTOM", True)
        add_idf_sdkconfig_option(
            "CONFIG_PARTITION_TABLE_CUSTOM_FILENAME", "partitions.csv"
        )
        add_idf_sdkconfig_option("CONFIG_COMPILER_OPTIMIZATION_DEFAULT", False)
        add_idf_sdkconfig_option("CONFIG_COMPILER_OPTIMIZATION_SIZE", True)

        # Increase freertos tick speed from 100Hz to 1kHz so that delay() resolution is 1ms
        add_idf_sdkconfig_option("CONFIG_FREERTOS_HZ", 1000)

        # Setup watchdog
        add_idf_sdkconfig_option("CONFIG_ESP_TASK_WDT", True)
        add_idf_sdkconfig_option("CONFIG_ESP_TASK_WDT_PANIC", True)
        add_idf_sdkconfig_option("CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0", False)
        add_idf_sdkconfig_option("CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU1", False)

        cg.add_platformio_option("board_build.partitions", "partitions.csv")
        if CONF_PARTITIONS in config:
            add_extra_build_file(
                "partitions.csv", CORE.relative_config_path(config[CONF_PARTITIONS])
            )

        for name, value in conf[CONF_SDKCONFIG_OPTIONS].items():
            add_idf_sdkconfig_option(name, RawSdkconfigValue(value))

        cg.add_define(
            "USE_ESP_IDF_VERSION_CODE",
            cg.RawExpression(
                f"VERSION_CODE({framework_ver.major}, {framework_ver.minor}, {framework_ver.patch})"
            ),
        )

        for component in conf[CONF_COMPONENTS]:
            source = component[CONF_SOURCE]
            if source[CONF_TYPE] == TYPE_GIT:
                add_idf_component(
                    name=component[CONF_NAME],
                    repo=source[CONF_URL],
                    ref=source.get(CONF_REF),
                    path=component.get(CONF_PATH),
                    refresh=component[CONF_REFRESH],
                )
            elif source[CONF_TYPE] == TYPE_LOCAL:
                _LOGGER.warning("Local components are not implemented yet.")

    elif conf[CONF_TYPE] == FRAMEWORK_ARDUINO:
        cg.add_platformio_option("framework", "arduino")
        cg.add_build_flag("-DUSE_ARDUINO")
        cg.add_build_flag("-DUSE_ESP8266_FRAMEWORK_ARDUINO")
        cg.add_build_flag("-Wno-nonnull-compare")
        cg.add_platformio_option("platform", conf[CONF_PLATFORM_VERSION])
        cg.add_platformio_option(
            "platform_packages",
            [f"platformio/framework-arduinoespressif8266@{conf[CONF_SOURCE]}"],
        )

        # Default for platformio is LWIP2_LOW_MEMORY with:
        #  - MSS=536
        #  - LWIP_FEATURES enabled
        #     - this only adds some optional features like IP incoming packet reassembly and NAPT
        #       see also:
        #  https://github.com/esp8266/Arduino/blob/master/tools/sdk/lwip2/include/lwipopts.h

        # Instead we use LWIP2_HIGHER_BANDWIDTH_LOW_FLASH with:
        #  - MSS=1460
        #  - LWIP_FEATURES disabled (because we don't need them)
        # Other projects like Tasmota & ESPEasy also use this
        cg.add_build_flag("-DPIO_FRAMEWORK_ARDUINO_LWIP2_HIGHER_BANDWIDTH_LOW_FLASH")

        if config[CONF_RESTORE_FROM_FLASH]:
            cg.add_define("USE_ESP8266_PREFERENCES_FLASH")

        if config[CONF_EARLY_PIN_INIT]:
            cg.add_define("USE_ESP8266_EARLY_PIN_INIT")

        # Arduino 2 has a non-standards conformant new that returns a nullptr instead of failing when
        # out of memory and exceptions are disabled. Since Arduino 2.6.0, this flag can be used to make
        # new abort instead. Use it so that OOM fails early (on allocation) instead of on dereference of
        # a NULL pointer (so the stacktrace makes more sense), and for consistency with Arduino 3,
        # which always aborts if exceptions are disabled.
        # For cases where nullptrs can be handled, use nothrow: `new (std::nothrow) T;`
        cg.add_build_flag("-DNEW_OOM_ABORT")

        cg.add_platformio_option(
            "board_build.flash_mode", config[CONF_BOARD_FLASH_MODE]
        )

        ver: cv.Version = CORE.data[KEY_CORE][KEY_FRAMEWORK_VERSION]
        cg.add_define(
            "USE_ARDUINO_VERSION_CODE",
            cg.RawExpression(f"VERSION_CODE({ver.major}, {ver.minor}, {ver.patch})"),
        )

        if config[CONF_BOARD] in BOARDS:
            flash_size = BOARDS[config[CONF_BOARD]][KEY_FLASH_SIZE]
            ld_scripts = ESP8266_LD_SCRIPTS[flash_size]

            if ver <= cv.Version(2, 3, 0):
                # No ld script support
                ld_script = None
            if ver <= cv.Version(2, 4, 2):
                # Old ld script path
                ld_script = ld_scripts[0]
            else:
                ld_script = ld_scripts[1]

            if ld_script is not None:
                cg.add_platformio_option("board_build.ldscript", ld_script)

    CORE.add_job(add_pin_initial_states_array)


# Called by writer.py
def copy_files():
    dir = os.path.dirname(__file__)
    post_build_file = os.path.join(dir, "post_build.py.script")
    copy_file_if_changed(
        post_build_file,
        CORE.relative_build_path("post_build.py"),
    )
