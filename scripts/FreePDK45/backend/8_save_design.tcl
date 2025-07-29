# Generate File
# set top_module $::env(TOP_NAME)
write_lef_abstract pnr_out/${TOP_NAME}_pnr.lef
write_lef_library pnr_out/${TOP_NAME}_lib.lef
#do_extract_model -view default pnr_out/${TOP_NAME}_pnr.lib
saveNetlist pnr_out/${TOP_NAME}_pnr.v
streamOut pnr_out/${TOP_NAME}_pnr.gds.gz

exec touch _Finished_
