#!/usr/bin/env python3
"""Read-only Blender spatial validator.

Run this file inside Blender, then call ``run_from_json(config_json)``. The
configuration may contain ``terrain_name`` and lists named ``trees``, ``rocks``,
``cameras``, and ``supports``. Every mesh list uses exact Blender object names;
collection-instance entries may also declare ``instance_root``.

The script evaluates dependency-graph meshes in world space and emits JSON. It
never changes scene data. Missing objects, geometry, or ray hits produce a
BLOCKED result rather than a false PASS.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import bpy
from mathutils import Vector

_TREE_MIN_EMBED_M = 0.02
_TREE_MAX_EMBED_M = 0.05
_ROCK_MIN_BURIAL_FRACTION = 0.02
_ROCK_MAX_BURIAL_FRACTION = 0.35
_CAMERA_MIN_CLEARANCE_M = 1.6
_CAMERA_MAX_CLEARANCE_M = 1.8
_SUPPORT_MIN_EMBED_M = 0.0
_SUPPORT_MAX_EMBED_M = 0.02
_VERTEX_EPSILON_M = 0.001
_RAY_MARGIN_M = 1.0
_RAY_DISTANCE_M = 1_000_000.0


def _number(value: float) -> float:
    return round(float(value), 6)


def _blocked(name: str, kind: str, message: str) -> dict[str, Any]:
    return {"name": name, "kind": kind, "result": "BLOCKED", "error": message}


def _mesh_world_vertices(obj: Any, matrix_world: Any, depsgraph: Any) -> list[Vector]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def _instance_parent_name(instance: Any) -> str | None:
    parent = getattr(instance, "parent", None)
    if parent is None:
        return None
    original = getattr(parent, "original", parent)
    return getattr(original, "name", None)


def _vertices_for_names(
    names: Iterable[str], depsgraph: Any, instance_root: str | None = None
) -> list[Vector]:
    vertices: list[Vector] = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        if instance_root is None:
            if obj.type == "MESH":
                evaluated = obj.evaluated_get(depsgraph)
                vertices.extend(_mesh_world_vertices(obj, evaluated.matrix_world, depsgraph))
            continue
        for instance in depsgraph.object_instances:
            instance_object = getattr(instance.object, "original", instance.object)
            if (
                instance_object.name == name
                and _instance_parent_name(instance) == instance_root
                and instance.object.type == "MESH"
            ):
                vertices.extend(
                    _mesh_world_vertices(instance.object, instance.matrix_world, depsgraph)
                )
    return vertices


def _base_point(vertices: list[Vector]) -> Vector:
    minimum_z = min(vertex.z for vertex in vertices)
    base_vertices = [vertex for vertex in vertices if vertex.z <= minimum_z + _VERTEX_EPSILON_M]
    count = len(base_vertices)
    return Vector(
        (
            sum(vertex.x for vertex in base_vertices) / count,
            sum(vertex.y for vertex in base_vertices) / count,
            minimum_z,
        )
    )


def _terrain_context(terrain_name: str, depsgraph: Any) -> tuple[Any, float]:
    terrain = bpy.data.objects.get(terrain_name)
    if terrain is None:
        raise ValueError(f"terrain object not found: {terrain_name}")
    if terrain.type != "MESH":
        raise ValueError(f"terrain object is not a mesh: {terrain_name}")
    evaluated = terrain.evaluated_get(depsgraph)
    vertices = _mesh_world_vertices(terrain, evaluated.matrix_world, depsgraph)
    if not vertices:
        raise ValueError(f"terrain has no evaluated vertices: {terrain_name}")
    return evaluated, max(vertex.z for vertex in vertices)


def _terrain_z(terrain: Any, terrain_max_z: float, x: float, y: float) -> float:
    origin_world = Vector((x, y, terrain_max_z + _RAY_MARGIN_M))
    inverse = terrain.matrix_world.inverted()
    origin_local = inverse @ origin_world
    direction_local = (inverse.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    hit, location, _normal, _face_index = terrain.ray_cast(
        origin_local, direction_local, distance=_RAY_DISTANCE_M
    )
    if not hit:
        raise ValueError(f"terrain ray missed at world XY ({x:.6f}, {y:.6f})")
    return float((terrain.matrix_world @ location).z)


def _contact_result(
    *,
    name: str,
    kind: str,
    vertices: list[Vector],
    support_z: float,
    minimum_embed: float,
    maximum_embed: float,
) -> dict[str, Any]:
    if not vertices:
        return _blocked(name, kind, "no evaluated contact mesh vertices found")
    base = _base_point(vertices)
    penetration = support_z - float(base.z)
    floating = max(0.0, -penetration)
    passed = minimum_embed <= penetration <= maximum_embed
    return {
        "name": name,
        "kind": kind,
        "support_z": _number(support_z),
        "contact_z": _number(base.z),
        "contact_x": _number(base.x),
        "contact_y": _number(base.y),
        "penetration_m": _number(max(0.0, penetration)),
        "floating_m": _number(floating),
        "minimum_embed_m": _number(minimum_embed),
        "maximum_embed_m": _number(maximum_embed),
        "result": "PASS" if passed else "FAIL",
    }


def _validate_tree(
    spec: dict[str, Any], terrain: Any, terrain_max_z: float, depsgraph: Any
) -> dict[str, Any]:
    name = str(spec.get("name", "<unnamed-tree>"))
    contact_objects = spec.get("contact_objects")
    if not isinstance(contact_objects, list) or not contact_objects:
        return _blocked(name, "tree", "contact_objects must name explicit trunk meshes")
    vertices = _vertices_for_names(contact_objects, depsgraph, spec.get("instance_root"))
    if not vertices:
        return _blocked(name, "tree", "no evaluated trunk contact geometry found")
    base = _base_point(vertices)
    try:
        support_z = _terrain_z(terrain, terrain_max_z, base.x, base.y)
    except ValueError as error:
        return _blocked(name, "tree", str(error))
    return _contact_result(
        name=name,
        kind="tree",
        vertices=vertices,
        support_z=support_z,
        minimum_embed=float(spec.get("min_embed_m", _TREE_MIN_EMBED_M)),
        maximum_embed=float(spec.get("max_embed_m", _TREE_MAX_EMBED_M)),
    )


def _validate_rock(
    spec: dict[str, Any], terrain: Any, terrain_max_z: float, depsgraph: Any
) -> dict[str, Any]:
    name = str(spec.get("name", "<unnamed-rock>"))
    object_names = spec.get("objects", [name])
    vertices = _vertices_for_names(object_names, depsgraph, spec.get("instance_root"))
    if not vertices:
        return _blocked(name, "rock", "no evaluated rock mesh vertices found")
    base = _base_point(vertices)
    try:
        support_z = _terrain_z(terrain, terrain_max_z, base.x, base.y)
    except ValueError as error:
        return _blocked(name, "rock", str(error))
    minimum_z = min(vertex.z for vertex in vertices)
    maximum_z = max(vertex.z for vertex in vertices)
    height = maximum_z - minimum_z
    if height <= 0.0:
        return _blocked(name, "rock", "evaluated rock height is zero")
    penetration = support_z - minimum_z
    burial_fraction = penetration / height
    minimum = float(spec.get("min_burial_fraction", _ROCK_MIN_BURIAL_FRACTION))
    maximum = float(spec.get("max_burial_fraction", _ROCK_MAX_BURIAL_FRACTION))
    return {
        "name": name,
        "kind": "rock",
        "support_z": _number(support_z),
        "base_z": _number(minimum_z),
        "height_m": _number(height),
        "penetration_m": _number(max(0.0, penetration)),
        "floating_m": _number(max(0.0, -penetration)),
        "burial_fraction": _number(burial_fraction),
        "minimum_burial_fraction": _number(minimum),
        "maximum_burial_fraction": _number(maximum),
        "result": "PASS" if minimum <= burial_fraction <= maximum else "FAIL",
    }


def _validate_camera(spec: dict[str, Any], terrain: Any, terrain_max_z: float) -> dict[str, Any]:
    name = str(spec.get("name", "<unnamed-camera>"))
    camera = bpy.data.objects.get(name)
    if camera is None or camera.type != "CAMERA":
        return _blocked(name, "camera", f"camera object not found: {name}")
    eye = camera.matrix_world.translation
    try:
        support_z = _terrain_z(terrain, terrain_max_z, eye.x, eye.y)
    except ValueError as error:
        return _blocked(name, "camera", str(error))
    clearance = float(eye.z) - support_z
    minimum = float(spec.get("min_clearance_m", _CAMERA_MIN_CLEARANCE_M))
    maximum = float(spec.get("max_clearance_m", _CAMERA_MAX_CLEARANCE_M))
    return {
        "name": name,
        "kind": "camera",
        "support_z": _number(support_z),
        "eye_z": _number(eye.z),
        "clearance_m": _number(clearance),
        "minimum_clearance_m": _number(minimum),
        "maximum_clearance_m": _number(maximum),
        "result": "PASS" if minimum <= clearance <= maximum else "FAIL",
    }


def _validate_support(spec: dict[str, Any], depsgraph: Any) -> dict[str, Any]:
    name = str(spec.get("name", "<unnamed-support-object>"))
    object_names = spec.get("objects", [name])
    vertices = _vertices_for_names(object_names, depsgraph, spec.get("instance_root"))
    return _contact_result(
        name=name,
        kind="support",
        vertices=vertices,
        support_z=float(spec.get("surface_z", 0.0)),
        minimum_embed=float(spec.get("min_embed_m", _SUPPORT_MIN_EMBED_M)),
        maximum_embed=float(spec.get("max_embed_m", _SUPPORT_MAX_EMBED_M)),
    )


def validate_scene(config: dict[str, Any]) -> dict[str, Any]:
    """Validate configured scene targets without changing Blender data."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    terrain_required = any(config.get(key) for key in ("trees", "rocks", "cameras"))
    terrain = None
    terrain_max_z = 0.0
    terrain_error = None
    if terrain_required:
        terrain_name = config.get("terrain_name")
        if not isinstance(terrain_name, str) or not terrain_name:
            terrain_error = "terrain_name is required for trees, rocks, or cameras"
        else:
            try:
                terrain, terrain_max_z = _terrain_context(terrain_name, depsgraph)
            except ValueError as error:
                terrain_error = str(error)

    results: list[dict[str, Any]] = []
    for kind, validator in (
        ("trees", _validate_tree),
        ("rocks", _validate_rock),
        ("cameras", _validate_camera),
    ):
        for spec in config.get(kind, []):
            name = str(spec.get("name", f"<unnamed-{kind[:-1]}>"))
            if terrain_error is not None or terrain is None:
                results.append(_blocked(name, kind[:-1], terrain_error or "terrain unavailable"))
            elif kind == "cameras":
                results.append(validator(spec, terrain, terrain_max_z))
            else:
                results.append(validator(spec, terrain, terrain_max_z, depsgraph))
    results.extend(_validate_support(spec, depsgraph) for spec in config.get("supports", []))

    states = {result["result"] for result in results}
    overall = "BLOCKED" if "BLOCKED" in states else "FAIL" if "FAIL" in states else "PASS"
    if not results:
        overall = "BLOCKED"
    return {
        "schema_version": 1,
        "result": overall,
        "target_count": len(results),
        "results": results,
    }


def run_from_json(config_json: str) -> str:
    """Parse a JSON configuration and return stable, formatted report JSON."""
    try:
        config = json.loads(config_json)
        if not isinstance(config, dict):
            raise ValueError("configuration must be a JSON object")
        report = validate_scene(config)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        report = {
            "schema_version": 1,
            "result": "BLOCKED",
            "target_count": 0,
            "error": str(error),
            "results": [],
        }
    return json.dumps(report, indent=2, sort_keys=True)
