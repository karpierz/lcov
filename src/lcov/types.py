from typing import TypeVar, Any, List, Dict

#ModuleAware = TypeVar('ModuleAware')

InfoEntry = Dict[str, object]

InfoData = Dict[str, InfoEntry]

BranchCountData = Dict[int, str]

ChecksumData = Dict[int, object]

BlockData = Dict["???", str]

LineData = Dict[object, BlockData]
#          Dict["???", Dict["???", str]]

#    Dict[int, Dict["???", Dict["???", str]]]
DB = Dict[int, LineData]

