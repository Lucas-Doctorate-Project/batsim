{
  description = "Batsim - Lucas Doctorate Project fork";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    kapack = {
      url = "github:oar-team/nur-kapack/master";
      flake = false;
    };
    simgrid = {
      url = "github:Lucas-Doctorate-Project/simgrid";
      inputs.flake-parts.follows = "flake-parts";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.kapack.follows = "kapack";
    };
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-darwin" ];

      perSystem = { inputs', pkgs, system, ... }:
        let
          kapackSet = import inputs.kapack { inherit pkgs; };
          baseStdenv =
            if builtins.elem system [ "x86_64-darwin" "aarch64-darwin" ]
            then pkgs.clangStdenv
            else pkgs.gccStdenv;
          stdenvFor = debug:
            if debug then pkgs.stdenvAdapters.keepDebugInfo baseStdenv else baseStdenv;
          fixedRedox = kapackSet.redox.overrideAttrs (old: {
            cmakeFlags =
              let
                baseCmakeFlags = old.cmakeFlags or [];
              in
              baseCmakeFlags ++ [ "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" ];
          });
          # gtest 1.17 needs C++17 CTAD but intervalset builds with -std=c++14,
          # so its unittest target fails to compile. Drop gtest so the test exe
          # is not built (gtest_dep.found() becomes false) and skip checks.
          fixedIntervalset = kapackSet.intervalset.overrideAttrs (old: {
            buildInputs = [];
            doCheck = false;
          });
          batschedForTests = (kapackSet.batsched.override { redox = fixedRedox; }).overrideAttrs (old: {
            src = pkgs.fetchFromGitLab {
              domain = "framagit.org";
              owner = "batsim";
              repo = "batsched";
              rev = "17072778995100fc90214ea4910bf5b171adfd0d";
              hash = "sha256-SHFfYw+xRqMN+bTHAVk9Wli/2xaJBEpG50YonklYKIs=";
            };
          });
          pybatsim = kapackSet.pybatsim-320.overrideAttrs (old: {
            src = pkgs.fetchFromGitLab {
              domain = "gitlab.inria.fr";
              owner = "batsim";
              repo = "pybatsim";
              rev = "880dd60c537d7d7a8246daaf5b2d1f7bfea3cbf4";
              hash = "sha256-ZKspUDkThX2MeqFqieDloAgrSh28tQ92KD3sjmDIQPU=";
            };
          });
          batexpe = kapackSet.batexpe or null;
          makeBatsim = { debug, doCoverage ? false, doUnitTests ? false, simgrid, werror ? false }:
            pkgs.callPackage ./nix/batsim.nix {
              batsimPackage = kapackSet.batsim;
              redox = fixedRedox;
              intervalset = fixedIntervalset;
              stdenv = stdenvFor debug;
              inherit debug doCoverage doUnitTests simgrid werror;
            };

          batsim = makeBatsim {
            debug = false;
            doCoverage = false;
            doUnitTests = false;
            simgrid = inputs'.simgrid.packages.default;
          };
          batsim-debug = makeBatsim {
            debug = true;
            doCoverage = false;
            doUnitTests = true;
            simgrid = inputs'.simgrid.packages.simgrid-debug;
          };
          batsim-coverage = makeBatsim {
            debug = true;
            doCoverage = true;
            doUnitTests = true;
            simgrid = inputs'.simgrid.packages.simgrid-coverage;
          };
          batsim-integration-tests = pkgs.callPackage ./nix/integration-tests.nix {
            batsim = batsim-debug;
            batsched = batschedForTests;
            inherit pybatsim batexpe;
            loguru = kapackSet.loguru;
          };
          batsim-integration-tests-coverage = pkgs.callPackage ./nix/integration-tests.nix {
            batsim = batsim-coverage;
            batsched = batschedForTests;
            inherit pybatsim batexpe;
            loguru = kapackSet.loguru;
            doCoverage = true;
            doUnitTests = true;
          };
          batsim-coverage-report = pkgs.callPackage ./nix/coverage-report.nix {
            batsim = batsim-coverage;
            integrationTests = batsim-integration-tests-coverage;
          };
        in {
          packages.default = batsim;
          packages.batsim = batsim;
          packages.batsim-debug = batsim-debug;
          packages.batsim-coverage = batsim-coverage;
          packages.batsim-integration-tests = batsim-integration-tests;
          packages.batsim-integration-tests-coverage = batsim-integration-tests-coverage;
          packages.batsim-coverage-report = batsim-coverage-report;

          devShells.default = pkgs.mkShell {
            inputsFrom = [ batsim-debug ];
            packages = [
              pkgs.meson
              pkgs.ninja
              pkgs.pkg-config
              pkgs.redis
              pybatsim
              batschedForTests
            ];
          };
        };
    };
}
