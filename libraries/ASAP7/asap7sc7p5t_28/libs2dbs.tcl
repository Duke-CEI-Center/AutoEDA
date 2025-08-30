set libdir LIB/CCS
mkdir LIB/CCS/DB
foreach f [glob -nocomplain $libdir/*.lib.gz] {
  read_lib $f
  set L [get_object_name [index_collection [get_libs *] end]]
  write_lib -format db -output [file join $libdir "${L}.db"] $L
  puts "Converted $f -> [file join $libdir ${L}.db]"
}
exit
