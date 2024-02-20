import time
from typing import Any

import ray
from ray.types import ObjectRef
from ray.util.actor_pool import ActorPool
from ray.util.metrics import Gauge

from data_processing.data_access.data_access import GB


class RayUtils:
    """
    Class implementing support methods for Ray execution
    """

    @staticmethod
    def get_available_resources(
        available_cpus_gauge: Gauge = None,
        available_gpus_gauge: Gauge = None,
        available_memory_gauge: Gauge = None,
        object_memory_gauge: Gauge = None,
    ) -> dict[str, Any]:
        """
        Get currently available cluster resources
        :param available_cpus_gauge: ray Gauge to report available CPU
        :param available_gpus_gauge: ray Gauge to report available GPU
        :param available_memory_gauge: ray Gauge to report available memory
        :param object_memory_gauge: ray Gauge to report available object memory
        :return: a dict of currently available resources
        """
        resources = ray.available_resources()
        if available_cpus_gauge is not None:
            available_cpus_gauge.set(int(resources.get("CPU", 0.0)))
        if available_gpus_gauge is not None:
            available_gpus_gauge.set(int(resources.get("GPU", 0.0)))
        if available_memory_gauge is not None:
            available_memory_gauge.set(resources.get("memory", 0.0) / GB)
        if object_memory_gauge is not None:
            object_memory_gauge.set(resources.get("object_store_memory", 0.0) / GB)
        return {
            "cpus": int(resources.get("CPU", 0.0)),
            "gpus": int(resources.get("GPU", 0.0)),
            "memory": resources.get("memory", 0.0) / GB,
            "object_store": resources.get("object_store_memory", 0.0) / GB,
        }

    @staticmethod
    def get_cluster_resources() -> dict[str, Any]:
        """
        Get cluster resources
        :return: cluster resources
        """
        resources = ray.cluster_resources()
        return {
            "cpus": int(resources.get("CPU", 0.0)),
            "gpus": int(resources.get("GPU", 0.0)),
            "memory": resources.get("memory", 0.0) / GB,
            "object_store": resources.get("object_store_memory", 0.0) / GB,
        }

    @staticmethod
    def create_actors(
        clazz: type, params: dict[str, Any], actor_options: dict[str, Any], n_actors: int, creation_delay: int = 0
    ) -> list[ObjectRef]:
        """
        Create a set of actors
        :param clazz: actor class, has to be annotated as remote
        :param params: actor init params
        :param actor_options: dictionary of actor options.
        see https://docs.ray.io/en/latest/ray-core/api/doc/ray.actor.ActorClass.options.html
        :param n_actors: number of actors
        :param creation_delay - delay between actor's creations
        :return: a list of actor handles
        """

        def operator() -> ObjectRef:
            time.sleep(creation_delay)
            return clazz.options(**actor_options).remote(params)

        return [operator() for _ in range(n_actors)]

    @staticmethod
    def process_files(
        executors: ActorPool,
        files: list[str],
        print_interval: int,
        files_in_progress_gauge: Gauge,
        files_completed_gauge: Gauge,
        available_cpus_gauge: Gauge,
        available_gpus_gauge: Gauge,
        available_memory_gauge: Gauge,
        object_memory_gauge: Gauge,
    ) -> None:
        """
        Process files
        :param executors: actor pool of executors
        :param files: list of files to process
        :param print_interval: print interval
        :param files_in_progress_gauge: ray Gauge to report files in process
        :param files_completed_gauge: ray Gauge to report completed files
        :param available_cpus_gauge: ray Gauge to report available CPU
        :param available_gpus_gauge: ray Gauge to report available GPU
        :param available_memory_gauge: ray Gauge to report available memory
        :param object_memory_gauge: ray Gauge to report available object memory
        :return:
        """
        RayUtils.get_available_resources(
            available_cpus_gauge=available_cpus_gauge,
            available_gpus_gauge=available_gpus_gauge,
            available_memory_gauge=available_memory_gauge,
            object_memory_gauge=object_memory_gauge,
        )
        running = 0
        t_start = time.time()
        completed = 0
        for path in files:
            if executors.has_free():  # still have room
                executors.submit(lambda a, v: a.process_table.remote(v), path)
                running = running + 1
                files_in_progress_gauge.set(running)
            else:  # need to wait for some actors
                executors.get_next_unordered()
                executors.submit(lambda a, v: a.process_table.remote(v), path)
                completed = completed + 1
                files_completed_gauge.set(completed)
                RayUtils.get_available_resources(
                    available_cpus_gauge=available_cpus_gauge,
                    available_gpus_gauge=available_gpus_gauge,
                    available_memory_gauge=available_memory_gauge,
                    object_memory_gauge=object_memory_gauge,
                )
                if completed % print_interval == 0:
                    print(f"Completed {completed} files in {(time.time() - t_start)/60} min")
        # Wait for completion
        files_completed_gauge.set(completed)
        # Wait for completion
        print(f"Completed {completed} files in {(time.time() - t_start)/60} min. Waiting for completion")
        while executors.has_next():
            executors.get_next_unordered()
            running -= 1
            completed += 1
            files_in_progress_gauge.set(running)
            files_completed_gauge.set(completed)
            RayUtils.get_available_resources(
                available_cpus_gauge=available_cpus_gauge,
                available_gpus_gauge=available_gpus_gauge,
                available_memory_gauge=available_memory_gauge,
                object_memory_gauge=object_memory_gauge,
            )

        print(f"Completed processing in {(time.time() - t_start)/60.} min")