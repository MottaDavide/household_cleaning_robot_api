# Metto qui i vari parser delle tipologie dell mappe e la funzione principale (che fa anche check)
from src.app.map.exceptions import InvalidMapContentError, UnsupportedExtensionError
from src.app.map.schemas import JsonMapSchema
from src.app.core import state
import json
from pathlib import Path

# seguo da txt map format nel pdf
def _parse_txt_map(text_content: str) -> tuple[dict, int, int]:
    
    normalized_text = text_content.replace("\r\n", "\n")
    if normalized_text.endswith("\n"):
        normalized_text = normalized_text[-1]
        
    lines = normalized_text.split("\n")
    rows = len(lines)
    
    # the map must contain at least one row and one column;
    if rows == 0 or lines[0] == "":
        raise InvalidMapContentError("The map must contain at least on row and one column.")
    cols = len(lines[0])
    if cols == 0:
        raise InvalidMapContentError("The map must contain at lease one column.")
    
    tiles_dict = {}
    for y, line in enumerate(lines): # the pdf state how to move, i.e. (x, y+1) -> to south
        #every row must be non-empty
        if line == "":
            raise InvalidMapContentError("Blank rows inside the map are not permitted.")
        
        
        # every row must have the same number of columns
        if len(line) != cols:
            raise InvalidMapContentError(f"Every row must have the same number of column. Error at row {i}, expected {cols} number of columns, got {len(line)}")
        
        
        # check chars (x or o)
        for x, char in enumerate(line):
            if char == 'o':
                tiles_dict[(x, y)] = {"walkable": True, "dirty": True}
            elif char == 'x':
                tiles_dict[(x, y)] = {"walkable": False, "dirty": False}
            else:
                raise InvalidMapContentError(f"Not valid character found at row {i}, column {j}. Expected 'x' or 'o', got {char} instead")
            
        
        return tiles_dict, rows, cols
    
    
# come sopra ma per il json
def _parse_json_map(content: bytes)-> tuple[dict, int, int]:
    try:
        data = json.load(content)
    except Exception as e:
        raise InvalidMapContentError(f"Not valid JSON format: {e}") from e
    
    # Pydantic check on JSON structure (rows and cols are poisitive integers, check in types os walkable and dirty)
    try:
        map_model = JsonMapSchema(**data)
    except Exception as e:
        raise InvalidMapContentError(f"Worng JSON strucutured: {e}") from e
    
    rows = map_model.rows
    cols = map_model.cols
    tiles_dict = {}
    for tile in map_model.tiles:
        # x and y are integers within the declared bounds;
        if not (0 < tile.x < cols and 0 < tile.y < rows):
            raise InvalidMapContentError(f"Coordinate ({tile.x}, {tile.y}) out of bound.")
        
        # each coordinate and duplicate coordinates are invalid;
        if (tile.x, tile.y) in tiles_dict:
            raise InvalidMapContentError(f"Coordinate ({tile.x}, {tile.y}) already present.")
        
        # walkable tile whose dirty field is omitted starts dirty;
        is_walkable = tile.walkable
        is_dirty = tile.dirty
        
        if is_walkable and is_dirty is None:
            is_dirty = True
        
        #a non-walkable tile must have dirty omitted or set to false ; setting it to true is invalid.
        if not is_walkable:
            if is_dirty:
                raise InvalidMapContentError(f"The tile related to coordinates ({tile.x}, {tile.y}) cannot be dirty ( dirty = True) because it is not walkable")
            else:
                is_dirty = False
                
        tiles_dict[(tile.x, tile.y)] = {"walkable": is_walkable, "dirty": is_dirty}
        
    # each coordinate appears exactly once—missing and duplicate coordinates are invalid;
    if len(tiles_dict) != rows*cols:
        raise InvalidMapContentError(f"Missing coordinate. Expected {rows*cols} values, got {len(tiles_dict)} instead.")
    
    return tiles_dict, rows, cols


# Funzione principale
def process_map_upload(filename: str, content: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    
    # extension check
    if extension not in ['.txt','.json']:
        raise UnsupportedExtensionError(f"File extension {extension} is not supported.")
    
    
    if extension == ".txt":
        text_content = content.decode("utf-8")
        tiles, rows, cols = _parse_txt_map(text_content=text_content)
        
    elif extension == ".json":
        tiles, rows, cols = _parse_json_map(content=content) 
        
    # overwriting the previous map
    state.current_map = tiles
    state.map_dimensions = {"rows": rows, "cols": cols}
    
    
    walkable_count = sum(1 for t in tiles.values() if t["walkable"])

    # come da pdf in caso di success
    return {
            "rows": rows,
            "cols": cols,
            "walkable_tiles": walkable_count
        }