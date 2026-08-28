// SPDX-License-Identifier: Apache-2.0

import 'dart:ffi';

@Native<Int32 Function(Int32, Int32)>(symbol: 'atlas_add')
external int atlasAdd(int left, int right);
