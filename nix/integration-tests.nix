{ lib
, stdenv
, python3Packages
, redis
, valgrind
, batsim
, batsched
, pybatsim
, loguru
, batexpe ? null
, doCoverage ? false
, doUnitTests ? false
, doValgrindAnalysis ? false
, version ? "unstable"
}:

stdenv.mkDerivation rec {
  pname = "batsim-integration-tests";
  inherit version;

  src = lib.sourceByRegex ../. [
    "^test"
    "^test/.*\.py"
    "^platforms"
    "^platforms/.*\.xml"
    "^workloads"
    "^workloads/.*\.json"
    "^workloads/.*\.dax"
    "^workloads/smpi"
    "^workloads/smpi/.*"
    "^workloads/smpi/.*/.*\.txt"
    "^workloads/usage-trace"
    "^workloads/usage-trace/.*"
    "^workloads/usage-trace/.*/.*\.txt"
    "^events"
    "^events/.*\.txt"
  ];

  buildInputs = with python3Packages; [
    batsim
    batsched
    redis
    pybatsim
    pytest
    pytest-html
    pandas
  ] ++ lib.optional (batexpe != null) batexpe
    ++ lib.optionals doValgrindAnalysis [ valgrind ];

  shellHook = lib.optionalString stdenv.isDarwin ''
    export DYLD_FALLBACK_LIBRARY_PATH=${loguru}/lib:$DYLD_FALLBACK_LIBRARY_PATH
  '';
  DYLD_FALLBACK_LIBRARY_PATH = lib.optionalString stdenv.isDarwin "${loguru}/lib";

  pytestArgs = "-ra test/ --html=./report/pytest_report.html"
    + lib.optionalString doValgrindAnalysis " --with-valgrind";

  preBuild = lib.optionalString doCoverage ''
    mkdir -p gcda
    export GCOV_PREFIX=$(realpath gcda)
    export GCOV_PREFIX_STRIP=${batsim.GCOV_PREFIX_STRIP}
  '' + lib.optionalString (doCoverage && doUnitTests) ''
    cp --no-preserve=all ${batsim}/gcda/*.gcda gcda/
  '';

  buildPhase = ''
    runHook preBuild
    set +e
    pytest ${pytestArgs}
    echo $? > ./pytest_returncode
    set -e
  '';

  checkPhase = ''
    pytest_return_code=$(cat ./pytest_returncode)
    echo "pytest return code: $pytest_return_code"
    if [ $pytest_return_code -ne 0 ] ; then
      exit 1
    fi
  '';
  doCheck = false;

  installPhase = ''
    mkdir -p $out
    mv ./report/* ./pytest_returncode $out/
  '' + lib.optionalString doCoverage ''
    mv ./gcda $out/
  '';
}
