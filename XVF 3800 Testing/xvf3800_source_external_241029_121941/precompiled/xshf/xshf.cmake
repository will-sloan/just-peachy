    add_library(xshf_imported STATIC IMPORTED)
    add_library(shf STATIC IMPORTED)
    set_property(TARGET xshf_imported PROPERTY IMPORTED_LOCATION ${CMAKE_CURRENT_LIST_DIR}/lib/libxshf.a)
    set_property(TARGET shf PROPERTY IMPORTED_LOCATION ${CMAKE_CURRENT_LIST_DIR}/lib/libBeClearSuperHandsFree.a)

    set_property(TARGET shf PROPERTY SYSTEM OFF)
    add_library(xshf INTERFACE)
    set_property(TARGET xshf PROPERTY SYSTEM OFF)
    target_include_directories(xshf INTERFACE ${CMAKE_CURRENT_LIST_DIR}/inc)
    target_link_libraries(xshf INTERFACE shf xshf_imported)
    target_compile_definitions(xshf INTERFACE SHF_NUM_BANDS=1)

    add_library(xshf::xshf ALIAS xshf)
