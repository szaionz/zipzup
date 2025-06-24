import base_classes
import json
from abc import ABC
from typing import List
import kan
import reshet
import keshet
import i24
import channel14
import knesset

def inheritors(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return [subclass for subclass in subclasses if not ABC in subclass.__bases__]

provider_classes = inheritors(base_classes.ChannelProvider)

with open('/app/channels.json', 'r') as f:
    channels_data = json.load(f)

channel_providers: List[base_classes.ChannelProvider] = []
for provider_class in provider_classes:
    channel_group = provider_class.channel_group
    for channel_json_obj in channels_data.get(channel_group, {}).get('channels', []):
        if channel_json_obj.get('enabled'):
            provider = provider_class(
                    **channel_json_obj,
                )
            channel_providers.append(
                provider
            )
            
