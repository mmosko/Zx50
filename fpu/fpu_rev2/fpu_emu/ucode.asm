; =======================
; Top-level include of all microcode source

.include "asm/add_f32.asm"
.include "asm/add_i32.asm"
.include "asm/add_i64.asm"

.include "asm/sub_f32.asm"
.include "asm/sub_i32.asm"
.include "asm/sub_i64.asm"

.include "asm/mul_f32.asm"
.include "asm/mul_i32.asm"
.include "asm/mul_i64.asm"

.include "asm/div_f32.asm"
.include "asm/div_i32.asm"

.include "asm/sqrt_f32.asm"
.include "asm/log2_f32.asm"
.include "asm/exp2_f32.asm"

.include "asm/chs_f32.asm"
.include "asm/chs_f64.asm"
.include "asm/chs_i32.asm"
.include "asm/chs_i64.asm"

.include "asm/abs_f32.asm"
.include "asm/abs_f64.asm"
.include "asm/abs_i32.asm"
.include "asm/abs_i64.asm"

.include "asm/dup4.asm"
.include "asm/dup8.asm"

.include "asm/push_const.asm"
.include "asm/cp_mem.asm"
