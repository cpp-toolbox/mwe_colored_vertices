import argparse
from PIL import Image
from typing import List, Dict, Union, Tuple
import os
import sys

from dataclasses import dataclass, field
from typing import List, Optional, Union, Tuple


@dataclass
class Position:
    x: float
    y: float
    z: float


@dataclass
class TexCoord:
    u: float
    v: float


@dataclass
class Normal:
    x: float
    y: float
    z: float


@dataclass
class FaceVertex:
    position_index: Optional[int] = None
    texcoord_index: Optional[int] = None
    normal_index: Optional[int] = None


@dataclass
class Face:
    vertices: List[FaceVertex]  # structured indices
    material: str  # material used
    line: str = ""  # original face line (optional)


@dataclass
class OBJ:
    positions: List[Position] = field(default_factory=list)
    texcoords: List[TexCoord] = field(default_factory=list)
    normals: List[Normal] = field(default_factory=list)
    faces: List[Face] = field(default_factory=list)
    out_lines: List[Union[Tuple[str, int], str]] = field(default_factory=list)
    # changes throughout parsing, the active material will apply to newly created faces
    current_material: str = ""


def parse_obj(file_path: str) -> OBJ:
    obj = OBJ()

    with open(file_path, "r") as f:
        for line in f:
            line_strip = line.strip()
            if line.startswith("v "):
                parts = line_strip.split()
                pos = Position(float(parts[1]), float(parts[2]), float(parts[3]))
                obj.positions.append(pos)
                obj.out_lines.append(("v", len(obj.positions) - 1))
            elif line.startswith("vt "):
                parts = line_strip.split()
                tex = TexCoord(float(parts[1]), float(parts[2]))
                obj.texcoords.append(tex)
                obj.out_lines.append(("vt", len(obj.texcoords) - 1))
            elif line.startswith("vn "):
                parts = line_strip.split()
                norm = Normal(float(parts[1]), float(parts[2]), float(parts[3]))
                obj.normals.append(norm)
                obj.out_lines.append(("vn", len(obj.normals) - 1))
            elif line_strip.lower().startswith("usemtl"):
                obj.current_material = line_strip.split(None, 1)[1]
                obj.out_lines.append(line)
            elif line_strip.lower().startswith("f "):
                face_vertices = []
                for vert in line_strip.split()[1:]:
                    # OBJ format: v/vt/vn or v//vn or v/vt or v
                    v_idx, vt_idx, vn_idx = None, None, None
                    parts = vert.split("/")
                    if len(parts) >= 1 and parts[0]:
                        v_idx = int(parts[0]) - 1
                    if len(parts) >= 2 and parts[1]:
                        vt_idx = int(parts[1]) - 1
                    if len(parts) == 3 and parts[2]:
                        vn_idx = int(parts[2]) - 1
                    face_vertices.append(FaceVertex(v_idx, vt_idx, vn_idx))

                face = Face(
                    vertices=face_vertices,
                    material=obj.current_material,
                    line=line_strip,
                )
                obj.faces.append(face)
                obj.out_lines.append(line)
            else:
                obj.out_lines.append(line)

    return obj


@dataclass
class Material:
    name: str
    ambient: Optional[List[float]] = None  # Ka
    diffuse: Optional[List[float]] = None  # Kd
    specular: Optional[List[float]] = None  # Ks
    shininess: Optional[float] = None  # Ns
    alpha: Optional[float] = None  # d
    illum: Optional[int] = None  # illum
    map_Ka: Optional[str] = None  # ambient texture map
    map_Kd: Optional[str] = None  # diffuse texture map
    map_Ks: Optional[str] = None  # specular texture map
    map_Ns: Optional[str] = None  # specular highlight map
    map_d: Optional[str] = None  # alpha map
    map_bump: Optional[str] = None  # bump map
    extra_props: Dict[str, Union[str, float, List[float]]] = field(default_factory=dict)


@dataclass
class MTL:
    materials: List[Material] = field(default_factory=list)
    out_lines: List[str] = field(default_factory=list)
    current_material: Optional[Material] = None


def parse_mtl(file_path: str) -> MTL:
    mtl = MTL()

    with open(file_path, "r") as f:
        for line in f:
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("#"):
                mtl.out_lines.append(line)
                continue

            parts = line_strip.split(None, 1)
            key = parts[0].lower()
            value = parts[1] if len(parts) > 1 else None

            assert value

            if key == "newmtl":
                mat = Material(name=value)
                mtl.materials.append(mat)
                mtl.current_material = mat
                mtl.out_lines.append(line)
            elif mtl.current_material:
                if key == "ka":
                    mtl.current_material.ambient = list(map(float, value.split()))
                elif key == "kd":
                    mtl.current_material.diffuse = list(map(float, value.split()))
                elif key == "ks":
                    mtl.current_material.specular = list(map(float, value.split()))
                elif key == "ns":
                    mtl.current_material.shininess = float(value)
                elif key == "d":
                    mtl.current_material.alpha = float(value)
                elif key == "illum":
                    mtl.current_material.illum = int(value)
                elif key == "map_ka":
                    mtl.current_material.map_Ka = value
                elif key == "map_kd":
                    mtl.current_material.map_Kd = value
                elif key == "map_ks":
                    mtl.current_material.map_Ks = value
                elif key == "map_ns":
                    mtl.current_material.map_Ns = value
                elif key == "map_d":
                    mtl.current_material.map_d = value
                elif key in ("map_bump", "bump"):
                    mtl.current_material.map_bump = value
                else:
                    # store unknown/extra properties
                    mtl.current_material.extra_props[key] = value

                mtl.out_lines.append(line)
            else:
                # lines before any 'newmtl' are kept for reference
                mtl.out_lines.append(line)

    return mtl


def sample_texture(image, u, v):
    w, h = image.size
    u_wrapped = u % 1.0
    v_wrapped = v % 1.0
    px = min(int(u_wrapped * w), w - 1)
    py = min(int((1.0 - v_wrapped) * h), h - 1)
    r, g, b = image.getpixel((px, py))[:3]
    return r / 255.0, g / 255.0, b / 255.0


def parse_args():
    p = argparse.ArgumentParser(
        description="Bake textures into per-vertex colors in an OBJ file."
    )
    p.add_argument("obj_in", help="Input OBJ file")
    p.add_argument("--mtl", help="Optional MTL file. Defaults to <objname>.mtl")
    p.add_argument(
        "--out", help="Optional output OBJ file. Default = <objname>_baked.obj"
    )
    return p.parse_args()


def ask_overwrite(path):
    print(f"[WARN] Output file '{path}' already exists.")
    ans = input("Overwrite? (y/n): ").strip().lower()
    if ans != "y":
        print("Aborted.")
        sys.exit(1)


def parse_mtl_file(mtl_path) -> Dict[str, str]:
    """Return a dict mapping material name → texture path."""
    if not os.path.isfile(mtl_path):
        print(f"[ERROR] MTL file not found: {mtl_path}")
        sys.exit(1)

    mat_to_tex = {}
    current_mat = None
    with open(mtl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("newmtl"):
                current_mat = line.split(None, 1)[1]
            elif current_mat and line.lower().startswith("map_kd"):
                tex = line.split(None, 1)[1]
                mat_to_tex[current_mat] = tex
    return mat_to_tex


def main():
    args = parse_args()
    obj_out = args.out if args.out else os.path.splitext(args.obj_in)[0] + "_baked.obj"
    if os.path.exists(obj_out):
        ask_overwrite(obj_out)

    mtl_path = args.mtl if args.mtl else os.path.splitext(args.obj_in)[0] + ".mtl"

    obj = parse_obj(args.obj_in)
    mtl = parse_mtl(mtl_path)

    print(f"[DONE] Wrote baked OBJ → {obj_out}")


if __name__ == "__main__":
    main()
