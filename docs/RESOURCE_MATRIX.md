# ScanToPath 2026 — Resource extraction matrix (2026-10-18)

Baseline: `01_PHAM_VI_VA_BAN_DO_NGHIEN_CUU.md` on user Drive (Sep 2026). Project is RGB-D -> metric/trusted geometry -> feature & relations -> engineering digital replica -> technical outputs, then task-aware active acquisition.

| Resource | Extract for ScanToPath | Integrate now? | Limit / verification |
|---|---|---|---|
| OrbbecSDK v2 | Native C/C++ RGB-D acquisition, intrinsics/extrinsics, stream alignment, device info, depth scale, frame timestamp, firmware, recording/replay where supported | YES - milestone capture adapter after device test | Requires Gemini 2 FW and actual SDK ABI/profile verification. No simulation as sensor. |
| PointCloudLibrary/PCL | Reference for outlier filtering, segmentation, normals, sample consensus, metrology algorithms | SELECTIVE / LATER | Existing target uses Open3D C++; do not import entire PCL alongside it without identified gap; dependency and build cost. |
| best-of-ml-python | Library discovery catalog | NO runtime | Catalog not an ML framework; track candidates after concrete need. |
| LocateAnything3D (NVLabs project) | Vision-language 3D bounding boxes/semantic object proposals | RESEARCH LATER | Inferred 3D bounding boxes are not metrology. Distinct from LocateAnything-3B. |
| NVIDIA LocateAnything-3B | Text-prompted RGB visual grounding/2D regions | OPTIONAL LATER | NVIDIA non-commercial model license; mask generation needs extra stage; not a depth/mesh model. |
| mudler/locate-anything.cpp | C++/ggml local runtime for preceding **2D** grounding model | OPTIONAL LATER | Read model-license separately from MIT wrapper; Q8 ~6.3GB so unsuitable for Pi 4 4GB baseline. |
| neilsonnn/image-blaster | Generative scene/object assets, exploration UI references | NO in metrology | Requires World Labs/FAL; generated meshes are not measured. |
| earthtojake/text-to-cad | Agent-assisted CAD export/geometry modeling workflow ideas | OPTIONAL output, not core | Text-to-CAD does not recover true CAD from measured specimen; keep human approval; telemetry privacy check. |
| viettranx/3dviz-pro-max | 3D scene/interaction design references (Three.js/Blender) | UX reference only | Target desktop is Qt6/VTK, not browser/WebGL runtime. |
| Robbyant/lingbot-map | Streaming reconstruction literature, pose/drift context | RESEARCH / OPTIONAL benchmark | Heavy CUDA/GPU and Python research runtime; not automatic replacement for motor encoder geometry and metric checks. |
| The supplied computer-vision 2026 infographic | Shortlist: RF-DETR/YOLO26 detector; DINOv3 embeddings; SAM3 segmentation; Depth Anything 3 depth | LATER controlled A/B tests | Illustration alone not enough to verify exact versions/weights/licenses. Direct Orbbec depth remains authoritative. |
| Nguyen et al. SPIE 2018 matching camera/mirror paper (arXiv:1908.06342) | Backprojection, mirror plane RANSAC+SVD, accuracy testing, point set processing | Reference math and validation | Mirror configuration differs from 2-axis object stage. |
| Nguyen et al. IEEE Access 2018 ToF + mirrors | Unreliable depth sample removal and multipath distortions, RMSE evaluation | Reference methodology | Gemini 2 is Active Stereo IR, not ToF; ToF-specific multipath algorithm not directly applicable. |
| Nguyen et al. Tech report 1380 | Dynamic point cloud reconstruction with two mirrors | Reference robustness | Contrasting physical system; do not copy as scanner baseline. |

## Priority / required extraction

P0: Orbbec SDK v2 + fixture-verified intrinsics/extrinsics/scale; C++20 geometric transforms; existing Open3D C++ / OpenCV C++ / Eigen / VTK toolkit.
P1: compare selective PCL algorithms if Open3D insufficient; evaluate use of 2D prompt-based detection to label mask regions.
P2: explore 3D semantic proposals, generative assets, text-to-CAD, large neural streaming systems after a trustworthy measured baseline.

## Source links

- Scope: https://drive.google.com/file/d/1xYSZv9Di3eAp_NGFKyTr8fv4faPETh14/view
- Orbbec: https://github.com/orbbec/OrbbecSDK_v2 and https://github.com/orbbec/OrbbecSDK_v2/releases
- PCL: https://github.com/PointCloudLibrary/pcl
- Discovery: https://github.com/lukasmasuch/best-of-ml-python
- LocateAnything3D: https://nvlabs.github.io/LocateAnything3D/
- NVIDIA LocateAnything-3B: https://huggingface.co/nvidia/LocateAnything-3B
- locate-anything.cpp: https://github.com/mudler/locate-anything.cpp
- image-blaster: https://github.com/neilsonnn/image-blaster
- text-to-cad: https://github.com/earthtojake/text-to-cad
- 3dviz-pro-max: https://github.com/viettranx/3dviz-pro-max
- LingBot-Map: https://github.com/robbyant/lingbot-map
- Gemini 2 technology: https://www.orbbec.com/products/structured-light-camera/gemini-2/
