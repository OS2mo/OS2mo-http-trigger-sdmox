# SPDX-FileCopyrightText: Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseSettings, HttpUrl
from pydantic.tools import parse_obj_as


class Settings(BaseSettings):
    mora_url: HttpUrl = parse_obj_as(HttpUrl, "https://morademo.magenta.dk/")
    saml_token: Optional[str]

    triggered_uuids: List[UUID]
    ou_levelkeys: List[str]
    ou_time_planning_mo_vs_sd: Dict[str, str]

    amqp_username: str
    amqp_password: str
    amqp_host: str = "msg-amqp.silkeborgdata.dk"
    amqp_virtual_host: str
    amqp_port: int = 5672
    amqp_check_waittime: int = 3
    amqp_check_retries: int = 6

    sd_username: str
    sd_password: str
    sd_institution: str
    sd_base_url: HttpUrl = parse_obj_as(HttpUrl, "https://service.sd.dk/sdws/")


def get_settings(**overrides):
    settings = Settings(**overrides)
    return settings
