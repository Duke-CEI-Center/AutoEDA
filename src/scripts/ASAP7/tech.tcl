#------------------------------------------------------------------------------
# Library Setup
#------------------------------------------------------------------------------

set PDK_DIR $env(BASE_DIR)/libraries/ASAP7
set STDLIB_DIR $PDK_DIR/asap7sc7p5t_28
set DB_DIR $STDLIB_DIR/DB/CCS
set LIB_DIR $STDLIB_DIR/LIB/CCS
set LEF_DIR $STDLIB_DIR/LEF
set QRC_DIR $STDLIB_DIR/qrc

# set fast_db [list $DB_DIR/fast.db]
set slow_db [list $DB_DIR/*SS*.db]
# set typical_db [list $DB_DIR/typical.db]

#set fast_lib [list $LIB_DIR/NangateOpenCellLibrary_fast_ccs.lib]
set slow_lib [list $LIB_DIR/*SS*.lib.gz]
#set typical_lib [list $LIB_DIR/NangateOpenCellLibrary_typical_ccs.lib]

#set nangate_lef [list $LEF_DIR/NangateOpenCellLibrary.lef]
# Metal/via LEF (process design rules)
set TECH_LEF  [lindex [glob -nocomplain \
    $LIBRARY_DIR/asap7sc7p5t_28/techlef_misc/*.lef] 0]
# Standard-cell LEFs (cell footprints/pins)
set SC_LEFS   [glob $LIBRARY_DIR/asap7sc7p5t_28/LEF/*.lef]
set asap7_lef [concat $TECH_LEF $SC_LEFS]

set qx_tech_file "$LIBRARY_DIR/asap7sc7p5t_28/qrc/qrcTechFile_typ03_scaled4xV06"
#set cap_tbl_file "$CAP_DIR/NCSU_FreePDK_45nm.capTbl"

set BUF_CELLS [list BUF_X1  BUF_X2  BUF_X4  BUF_X8  BUF_X16 BUF_X32]
set CLKBUF_CELLS [list CLKBUF_X1 CLKBUF_X2 CLKBUF_X3]
set CLKGT_CELLS [list CLKGATE_X1 CLKGATE_X2 CLKGATE_X4 CLKGATE_X8]
set INV_CELLS [list INV_X1  INV_X2  INV_X4  INV_X8  INV_X16  INV_X32]
set FILL_CELLS [list FILLCELL_X1  FILLCELL_X2  FILLCELL_X4  FILLCELL_X8  FILLCELL_X16  FILLCELL_X32]