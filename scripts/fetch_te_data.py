"""Download the Tennessee Eastman simulation runs the Ignition replay server uses, and check them.

Source: the Braatz group's open TE data (University of Illinois, NCSA-style license), via the same GitHub mirror
scripts/verify_te_source.py uses for teprob.f. Each file is checked against the SHA-256 recorded when this project
first used it, so a changed upstream file is caught instead of silently replayed.

  d00_te.dat  normal operation, 960 samples (3 simulated minutes each)
  d06_te.dat  fault IDV(6), loss of A feed

With --all it also fetches the rest of the published set, for the fault-detection evaluation
(scripts/fault_detection_eval.py): the training files d00.dat-d21.dat and the test files d01_te.dat-d21_te.dat
(fault IDV(n) switched on at sample 160 of 960). The default stays the two replay files, so the Docker replay image
does not grow. All 44 recorded checksums were taken from files that are byte-identical to the Braatz group's own
archive (https://web.mit.edu/braatzgroup/TE_process.zip, checked 2026-10-12; journal entry 39).

Usage: python scripts/fetch_te_data.py [--all]
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "external" / "te-braatz"
BASE = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/"
FILES = {
    "d00_te.dat": "57d56da4199e3d73582855d810be1d13d931386fd728bf1694798c7b0a03678c",
    "d06_te.dat": "8a3adc7121eaa9b9300c27f9c57a8ab356315401cb964310a4a8244dd34bf79d",
}
# The rest of the published set, used only by the fault-detection evaluation (--all).
EVALUATION_FILES = {
    "d00.dat": "4c3c0b11eefacf93e5d2529e2866d7a625e37aa9153d0f95fae17a6c9e560deb",
    "d01.dat": "b0da22ac7561d82b0ba0b48bf87d2b3a8655cb23a3dc37330dd03cdd126c387c",
    "d01_te.dat": "e7e6992fb39664e739fccbc001a1c5d5f7cb21829544f734ca3f282c26f680e5",
    "d02.dat": "af1a46ba3a5482be3e7b143606f22ae509138544af2a2d0eb7389459257f8179",
    "d02_te.dat": "a34bd9c3693fa96bd3ee533fb7fbe29a9d226a4e3250b585ef1308e1136dbfb0",
    "d03.dat": "df39c57bdac7ea476ee236c289e0f59b0cbf868adfbbbaf213f692d8cd96e52a",
    "d03_te.dat": "b7bf6f2ed7cff0a5577898b009edd252b9bdf6ee9ff7dbeacf9af9aa4c6abace",
    "d04.dat": "346702fce33d9707f0b4ec5b8f533ccb08be60313607d5156d7e237b80a87b3f",
    "d04_te.dat": "1ccb488dd5feac11aad54623451168abef066229e685872597897800363916f9",
    "d05.dat": "3a47bfce4010ce0c634ae828409cce657ecd03bf0c4d59f8dd4a3d4f792f493f",
    "d05_te.dat": "1def7258a2865aeead699d52c8cf926fbf34c1467aaf298121987ab858fd0888",
    "d06.dat": "ff0882a44bb74f5d2d1a864425ac7e5ae82420391c7060232cefc08ad5bf7331",
    "d07.dat": "e3fd272ed53f899ab0c8278c7eede55418b01a2339b5fcff14a87fefaa3d181d",
    "d07_te.dat": "e01b7c81daf9fccc4495cbde5658296918276b3c078044893f6e945dd91d3446",
    "d08.dat": "4817735e339449bec909d1cbe77e421acc79c7357b8c6b5bb82c6e5788b72449",
    "d08_te.dat": "c0637f02f23b79890b43cfee9604818ad6d7f81532223d76acf1da0d6e2a2cc1",
    "d09.dat": "cb9146da760cdd52cad575d745413a5cfb4b447af2db9fb6a424cf6881ff0fcd",
    "d09_te.dat": "513df6c3a4fd48e0eaddb0002cd8cdab3a78a5c83c47883bb52d2dc6c2472428",
    "d10.dat": "e08697b5d074aea2345434bc4d26296f5dbdbb7efbf37a1bbee292b2ce765e8f",
    "d10_te.dat": "3a278be79d8d111fc60be3cfb4f961c28e2dc632f17eb519886aa0f95864ffc6",
    "d11.dat": "8294734d6f6e8f6b8643b9dc72f38ce40afd868d30dee9368a0d26b963a0af9f",
    "d11_te.dat": "6d60a4c932d918e1ab26ae5d16320936a665f3aad3f05482d23f5c4550b9f29a",
    "d12.dat": "62fcb3c71c0eda8eaaaf707f35296e60b17baaf9a9aef588687532cf4c560d38",
    "d12_te.dat": "2180fcecb01d1b110b429ba2969d6b18dcc625599e3640e54f69afa32dccbe50",
    "d13.dat": "f755d4ab6dc1d30e36c2e4604eeb0baff4b91032f487398b97fb1220eda861dd",
    "d13_te.dat": "2e34e0c427d6e41d77d6cae76550b7e95004f9f13bc093278ecf5c282a1c9f03",
    "d14.dat": "29fda7d5cae58cb7240e569e2d2d436371d077d282187d9205c7dc01df8755af",
    "d14_te.dat": "e8976d056c0769cebbcec3bcba89d2468040ccae7acbea55ebc3b2e56b217396",
    "d15.dat": "4c82fe0864cce2521e91a2c3e59d8630627c5e633cffe83f5e34ebc9901b5bca",
    "d15_te.dat": "a7242b956837bec8ca7f224d01805247f2aea6ea868eaa064e068b5c0761b1e5",
    "d16.dat": "ca1dfc5e31292052e83dcf6b4f60a73da197eb8a47e65d908ed7ac3cbcccb007",
    "d16_te.dat": "8381d7371aac49b498e7bf93149b77a0a6bbeffe73520881dcbe8ae96277244d",
    "d17.dat": "596aad6421a64d257bfa098cd5c4664d46dc49d88d1bad86cbc9518e6cd69e42",
    "d17_te.dat": "27d2d72052064e3cbb7a45df8073f15bb83b77403f532616e73c8869b043e7c9",
    "d18.dat": "b4d182c070036104cf150bc33f7aa879805f19943eb298bc05bdc8647dc70291",
    "d18_te.dat": "1db5b93a7daa58ed1b641845b58ad818546ced7f3de866c086da18a7ebef5041",
    "d19.dat": "ee3d2a50285cb3ba5e52ec05ea7cb39dc2b574bec592af9d44c192be132aeea6",
    "d19_te.dat": "c24dd77f787f89347273addc8a453d79f0b99edd64d43be11a5e0907bd515c5f",
    "d20.dat": "acdfe6c256fa6de74a811d6c7df1b710a9f0ed60f48242be92f3fa30db3df6b3",
    "d20_te.dat": "e54035eda95311f13dd095f87607d97a89b7541afa2a3f68af098f33a5e2e6e5",
    "d21.dat": "f34a9fefffef04ef1f49b3fb74e3def0010cda27a8577d814dd50604e2f8dc09",
    "d21_te.dat": "b6823aa09638cd59cb168bc24f991b6d4d557d8aea62b0b2a87ee67c21ba5a83",
}


def main(all_files=False):
    DEST.mkdir(parents=True, exist_ok=True)
    for name, want in ({**FILES, **EVALUATION_FILES} if all_files else FILES).items():
        path = DEST / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
            print(f"{name}: already present, checksum OK")
            continue
        with urllib.request.urlopen(BASE + name, timeout=60) as r:
            data = r.read()
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            raise SystemExit(f"{name}: checksum mismatch (got {got[:16]}..., expected {want[:16]}...). Not saved.")
        path.write_bytes(data)
        print(f"{name}: downloaded, {len(data):,} bytes, checksum OK")


if __name__ == "__main__":
    main(all_files="--all" in sys.argv[1:])
