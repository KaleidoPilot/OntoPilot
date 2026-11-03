
from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _template_project_statements():
    return yaml.safe_load((Path(__file__).parent/'sql.yaml').read_text(encoding='utf-8'))['template_catalog']


def get_template_project_sql(key):
    return _template_project_statements()[key]
