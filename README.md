# ac-expander

[AtCoder](https://atcoder.jp)で自作ライブラリを使うためのツール。

CPython及びCythonで書かれたモジュールを1ファイルに展開し、AtCoderに提出できるようにします。

## Install

```sh
python -m pip install git+https://github.com/bayashi-cl/ac-expander
```

## Usage

```sh
python -m ac-expander SOURCE [-o OUTPUT] [-m MODULE_NAMES]
```

* SOURCE: 展開したいファイル
* OUTPUT: 出力ファイル（指定されてない場合は標準出力）
* MODULE_NAMES: 展開するモジュール名（複数可）

## Exmple

[EDPC H - Grid 1](https://atcoder.jp/contests/dp/tasks/dp_h)

ModintライブラリをCythonで書いています。

### Original code

```python
from byslib.core.config import procon_setup
from byslib.core.const import MOD7
from byslib.core.fastio import readline, sinput
from cyslib.numeric.modint import Modint, set_mod


@procon_setup
def main(**kwargs) -> None:
    set_mod(MOD7)
    h, w = map(int, readline().split())
    a = [sinput() for _ in range(h)]
    dp = [[Modint() for _ in range(w)] for _ in range(h)]
    dp[0][0] += Modint(1)
    for i in range(h):
        for j in range(w):
            if a[i][j] == "#":
                continue
            if i + 1 != h and a[i + 1][j] == ".":
                dp[i + 1][j] += dp[i][j]
            if j + 1 != w and a[i][j + 1] == ".":
                dp[i][j + 1] += dp[i][j]

    print(dp[-1][-1])


if __name__ == "__main__":
    t = 1
    # t = int(readline())
    main(t)
```

### Submission

<https://atcoder.jp/contests/dp/submissions/30988494>

## How it Works

次のようなコードが冒頭に追加されます。

```python
from __future__ import ... # future文は先頭に必要
# ここから追加
import sys

if sys.argv[-1] == "ONLINE_JUDGE":
    import textwrap
    import pathlib

    import numpy as np
    from Cython.Build import cythonize
    from setuptools import Extension, setup

    path = pathlib.Path("relpath/to/cython_module.pyx")
    code = """\
    # Cython module code is expanded here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(code))

    path = pathlib.Path("relpath/to/python_module.pyx")
    code = """\
    # Python module code expanded here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(code))

    extensions = Extension(
        "*",
        ["./**/*.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3"],
    )
    setup(
        ext_modules=cythonize([extensions]),
        script_args=["build_ext", "--inplace"],
    )

# ここまで

import relpath.to.cython_module
import relpath.to.python_module

...

```

コンパイルフェーズ中にモジュールのコードをジャッジサーバーにコピーし、必要なら`.pyx`ファイルのコンパイルを行っています。

## Note

生成されたコードはAtCoderのPython上でのみ動作します。CodeForcesやPypy環境で自作ライブラリの展開をしたい場合は[expander](https://github.com/bayashi-cl/expander)を使ってください。
