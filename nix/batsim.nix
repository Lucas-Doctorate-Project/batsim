{ lib
, stdenv
, gtest
, batsimPackage
, redox
, intervalset
, simgrid
, debug ? false
, doCoverage ? false
, doUnitTests ? false
, werror ? false
}:

(batsimPackage.override {
  inherit debug intervalset redox simgrid stdenv;
}).overrideAttrs (old: rec {
  src = lib.sourceByRegex ../. [
    "^src"
    "^src/.*\.?pp"
    "^src/unittest"
    "^src/unittest/.*\.?pp"
    "^meson\.build"
    "^meson_options\.txt"
  ];

  patches = [];
  buildInputs = (old.buildInputs or []) ++ lib.optionals doUnitTests [ gtest.dev ];
  mesonBuildType = if debug then "debug" else "release";
  mesonFlags = [ "--warnlevel=3" ]
    ++ lib.optional werror "--werror"
    ++ lib.optional doUnitTests "-Ddo_unit_tests=true"
    ++ lib.optional doCoverage "-Db_coverage=true";
  ninjaFlags = [ "-v" ];

  doCheck = doUnitTests;
  checkPhase = ''
    meson test --print-errorlogs
  '';

  postInstall = lib.optionalString doCoverage ''
    mkdir -p $out/gcno
    cp batsim.p/*.gcno $out/gcno/
    cp libbatlib.a.p/*.gcno $out/gcno/
  '' + lib.optionalString (doCoverage && doUnitTests) ''
    mkdir -p $out/gcda
    cp libbatlib.a.p/*.gcda $out/gcda/
  '';

  passthru =
    let
      debugSrcDirs = [ "${src}/src" ];
    in
    (old.passthru or {}) // {
      hasUnitTests = doUnitTests;
      hasDebugSymbols = debug;
      hasCoverage = doCoverage;
      GCOV_PREFIX_STRIP = "5";
      DEBUG_SRC_DIRS = debugSrcDirs;
      GDB_DIR_ARGS = map (path: "--directory=" + path) debugSrcDirs;
    };
})
