import os
import sys

from coalesce_transform import CoalesceTransformConfiguration
from data_processing.ray import TransformLauncher
from data_processing.utils import DPFConfig, ParamsUtils


print(os.environ)
# create launcher
launcher = TransformLauncher(transform_runtime_config=CoalesceTransformConfiguration())
s3_cred = {
    "access_key": DPFConfig.S3_ACCESS_KEY,
    "secret_key": DPFConfig.S3_SECRET_KEY,
    "cos_url": "https://s3.us-east.cloud-object-storage.appdomain.cloud",
}

# Configure lakehouse unit test tables
lakehouse_config = {
    "lh_environment": "STAGING",
    "input_table": "academic.ieee_splitfile_test",
    "input_dataset": "",
    "input_version": "main",
    "output_table": "academic.ieee_coalesce_test",
    "output_path": "lh-test/tables/academic/ieee_coalesce_test",
    "token": DPFConfig.LAKEHOUSE_TOKEN,
}
worker_options = {"num_cpus": 0.8}
code_location = {"github": "github", "commit_hash": "12345", "path": "path"}
params = {
    "run_locally": True,
    "max_files": -1,
    "s3_cred": ParamsUtils.convert_to_ast(s3_cred),
    "lh_config": ParamsUtils.convert_to_ast(lakehouse_config),
    "worker_options": ParamsUtils.convert_to_ast(worker_options),
    "num_workers": 1,
    "checkpointing": False,
    "pipeline_id": "pipeline_id",
    "job_id": "job_id",
    "creation_delay": 0,
    "code_location": ParamsUtils.convert_to_ast(code_location),
    "coalesce_target": 100,
}
sys.argv = ParamsUtils.dict_to_req(d=params)
# for arg in sys.argv:
#     print(arg)

# launch
launcher.launch()