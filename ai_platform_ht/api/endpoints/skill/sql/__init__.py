
from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _template_statements():
    return yaml.safe_load((Path(__file__).parent/'sql.yaml').read_text(encoding='utf-8'))


def get_template_sql(key):
    group, name = key.split('.',1)
    return _template_statements()[group][name]
