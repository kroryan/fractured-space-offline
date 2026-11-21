"""Inventory geometric connected components without changing reviewed source data."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'obj/tooling/python'))
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('workshop_id')
    args = parser.parse_args()
    folder = ROOT / 'obj/expanse-authoring' / args.workshop_id
    metadata = json.loads((folder / 'prepared.json').read_text())
    archive = np.load(folder / 'geometry-0.npz')
    results = []
    for section in range(int(archive['mesh_count'])):
        points = archive[str(section) + '_positions'] * metadata['unit_metres']
        faces = archive[str(section) + '_triangles']
        unique, inverse = np.unique(points, axis=0, return_inverse=True)
        indices = inverse[faces]
        row = indices.ravel()
        col = indices[:, [1, 2, 0]].ravel()
        graph = coo_matrix((np.ones(len(row), dtype=np.uint8), (row, col)), shape=(len(unique), len(unique))).tocsr()
        count, labels = connected_components(graph, directed=False)
        sizes = np.bincount(labels[indices[:, 0]], minlength=count)
        lower, upper = np.full((count, 3), np.inf), np.full((count, 3), -np.inf)
        np.minimum.at(lower, labels, unique)
        np.maximum.at(upper, labels, unique)
        for component in np.flatnonzero(sizes > 0):
            results.append({'section': section, 'component': int(component), 'triangles': int(sizes[component]),
                'material': metadata['materials'][int(archive[str(section) + '_material'])],
                'center': ((lower[component] + upper[component]) / 2).tolist(),
                'size': (upper[component] - lower[component]).tolist(),
                'lower': lower[component].tolist(), 'upper': upper[component].tolist()})
        np.savez_compressed(folder / ('components-' + str(section) + '.npz'), face_component=labels[indices[:, 0]])
        print('Section', section, ':', count, 'components;', int(np.sum(sizes >= 50)), 'with at least 50 triangles', flush=True)
    (folder / 'component-review.json').write_text(json.dumps(results, indent=2))
    print('Saved geometric component inventory; weapon classification requires visual review.')


if __name__ == '__main__':
    main()
