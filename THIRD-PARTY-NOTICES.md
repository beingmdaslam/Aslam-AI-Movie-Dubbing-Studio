# Third-party notices

## Supertonic browser helper code

The file `supertonic-helper.js` is adapted from the archived Supertonic web example:

- Source: https://github.com/supertone-oss-archive/supertonic/tree/main/web
- Copyright (c) 2025 Supertone Inc.
- License: MIT

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

## Supertonic 3 model weights

The optional multilingual model and its ten preset voice styles are downloaded from the archived Supertone Hugging Face repository:

- Model: https://huggingface.co/supertone-oss-archive/supertonic-3
- License: OpenRAIL-M (https://huggingface.co/supertone-oss-archive/supertonic-3/blob/main/LICENSE)

The model is a separate artifact from the MIT-licensed browser helper code. Review the OpenRAIL-M restrictions and attribution requirements before redistribution or commercial use.

## Meta MMS text-to-speech models

The optional MMS models are community ONNX conversions of Meta MMS checkpoints. The underlying model weights are licensed CC-BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0). They are for non-commercial use only unless separate permission is obtained. Model cards are available at https://huggingface.co/Xenova.

## FFmpeg WebAssembly

- `@ffmpeg/ffmpeg` 0.12.15 wrapper: MIT license.
- `@ffmpeg/core` 0.12.10: GPL-2.0-or-later license (https://github.com/ffmpegwasm/ffmpeg.wasm/tree/main/packages/core).

The browser downloads the FFmpeg engine at runtime from jsDelivr. Anyone redistributing the application or binaries must review and comply with the applicable FFmpeg license terms.

## Other browser runtimes

- ONNX Runtime Web: MIT license.
- Transformers.js: Apache License 2.0.

These runtimes are fetched from their public package CDNs at runtime. Their respective license texts are available in their upstream repositories.
