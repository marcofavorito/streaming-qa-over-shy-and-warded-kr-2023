import re
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import List, Dict, Callable

from benchmark import ORIGINAL_DATASETS_DIR, ORIGINAL_PROGRAMS_DIR, CHASEBENCH_SCENARIOS
from benchmark.datasets.core import Dataset, DATA_SUBDIR_NAME, QUERIES_SUBDIR_NAME, DatasetID
from benchmark.datasets.translate import write_lines_for_vadalog, transform_dataset_file_with_header, \
    process_program_for_vadalog, process_program_for_dlve, process_program_for_vadalog_with_original_query
from benchmark.tools import ToolID
from benchmark.utils.base import remove_dir_or_fail

ONTOLOGY_256_DATASET_DIR = ORIGINAL_DATASETS_DIR / "ontology-256"
ONTOLOGY_256_PROGRAM_DIR = ORIGINAL_PROGRAMS_DIR / "ontology-256"


dataset_handlers: Dict[ToolID, Callable] = {
    ToolID.VADALOG: write_lines_for_vadalog,
    ToolID.VADALOG_PARSIMONIOUS_NAIVE: write_lines_for_vadalog,
    ToolID.VADALOG_PARSIMONIOUS_AGGREGATE: write_lines_for_vadalog,
    ToolID.DLVE: transform_dataset_file_with_header,
}

program_handler: Dict[ToolID, Callable] = {
    ToolID.VADALOG: process_program_for_vadalog,
    ToolID.VADALOG_PARSIMONIOUS_NAIVE: process_program_for_vadalog,
    ToolID.VADALOG_PARSIMONIOUS_AGGREGATE: process_program_for_vadalog,
    ToolID.VADALOG_RESUMPTION: process_program_for_vadalog_with_original_query,
    ToolID.VADALOG_PARSIMONIOUS_NAIVE_RESUMPTION: process_program_for_vadalog_with_original_query,
    ToolID.VADALOG_PARSIMONIOUS_AGGREGATE_RESUMPTION: process_program_for_vadalog_with_original_query,
    ToolID.DLVE: process_program_for_dlve,
}


def job(output_dataset_dir, dataset_handler, dataset_file):
    print(f"Processing dataset file {dataset_file}")
    output_dataset_file = output_dataset_dir / (dataset_file.stem + ".data")
    dataset_handler(
        dataset_file,
        output_dataset_file,
        header=None,
        predicate_name=dataset_file.stem,
    )


class Ontology256Dataset(Dataset):

    is_partitioned = False
    _IGNORE_QUERIES = {"q04", "q05", "q07", "q10", "q12", "q14", "q15", "q16", "q18", "q20"}

    @classmethod
    def process_dataset(cls, input_dir: Path, output_dir: Path, force: bool = True):
        dataset_name = input_dir.name
        output_dataset_dir = output_dir / dataset_name

        for tool in [ToolID.DLVE, ToolID.VADALOG]:
            dataset_handler = dataset_handlers[tool]
            tool_output_dataset_dir = output_dataset_dir / tool.value / DATA_SUBDIR_NAME
            remove_dir_or_fail(tool_output_dataset_dir, force)
            tool_output_dataset_dir.mkdir(parents=True, exist_ok=True)
            job_i = partial(job, tool_output_dataset_dir, dataset_handler)
            with Pool() as pool:
                pool.map(job_i, input_dir.iterdir())

    @classmethod
    def process_program(cls, input_dir: Path, output_dir: Path, force: bool = True):
        for tool in ToolID:
            current_output_dir = output_dir / input_dir.name / tool.value / QUERIES_SUBDIR_NAME
            remove_dir_or_fail(current_output_dir, force)
            current_output_dir.mkdir(parents=True, exist_ok=True)
            for program in sorted(input_dir.glob(f"program_q*.vada")):
                program_txt = program.read_text()
                query_name = re.search("q[0-9]+", program.name).group(0)
                if query_name in cls._IGNORE_QUERIES:
                    continue

                # remove q12 as it is bugged
                program_txt = re.sub("%?q12.*", "", program_txt)
                query_name_for_chasebench_file = query_name.replace("q0", "q")
                chasebench_query_file = CHASEBENCH_SCENARIOS / "Ontology-256" / "queries" / (query_name_for_chasebench_file + ".txt")
                output_content = program_handler[tool](program_txt, chasebench_query_file.read_text())
                output_file = current_output_dir / (query_name + ".txt")
                output_file.write_text(output_content)
