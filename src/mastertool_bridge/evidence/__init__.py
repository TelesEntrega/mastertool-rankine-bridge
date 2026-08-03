"""Evidence Bundle — o pacote de evidência de uma execução (fase R2).

Ver `bundle.py`. O caminho deste pacote é o nomeado em `docs/ROADMAP.md` §2.7,
e o substituto do stub `changes/package_builder.py`.
"""

from mastertool_bridge.evidence.bundle import (  # noqa: F401
    BUNDLE_LAYOUT,
    BundleError,
    BundleManifest,
    BundleVerification,
    EvidenceBundle,
    SECTIONS,
    verify_bundle,
)
