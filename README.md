# Hi, I'm Haochen Liu 👋
PhD Candidate in Computational Mathematics at the University of Macau  @ University of Macau.

I develop and investigate numerical methods for incompressible two-phase flows,
with a focus on phase-wise mass preservation, fully implicit finite element
discretizations, and scalable nonlinear/linear solvers.

My work connects mathematical modeling, numerical algorithm design,
C++ solver implementation, and verification through convergence studies
and large-scale parallel experiments.
 
Focusing on **phase-field models**, **mass-preserving schemes**, and **high-performance finite element methods** for incompressible two-phase flows.


## 🔬 Research Highlights

### Separate mass-preserving and fully coupled two-phase flow simulation

**Research challenge.** Maintaining phase-wise mass constraints during interface
deformation and topological changes, while solving the coupled flow and
phase-field equations reliably over long simulation times.

**Numerical approach.** The SMP-ACNS formulation uses Heaviside-based phase
constraints and two Lagrange multipliers. The numerical algorithm combines
a fully implicit Crank–Nicolson finite element discretization with
phase-wise mass projection after the nonlinear solve.

**Implementation work.** I implement and test the coupled solver in C++ using
libMesh and PETSc, including discrete residual evaluation, approximate
analytic Jacobian assembly, multiplier updates, and the integration of
Newton–Krylov–Schwarz iterations with mass correction.

**Verification.** I use manufactured-solution convergence tests and benchmark
problems involving bubble merging, rising, and three-dimensional pinch-off.
The numerical assessment includes interface evolution, phase-wise mass
variation, energy behavior, and parallel scalability.


[GitHub](https://github.com/LHappyCureall) · [Repositories](https://github.com/LHappyCureall?tab=repositories) · [Email](mailto:l18340091052@gmail.com) · [Simulation gallery](#-simulation-gallery)

## 📈 GitHub at a Glance

<!-- PROFILE-STATS:START -->
<a href="https://github.com/LHappyCureall">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-dark-6484ef97c56ff916.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-light-6484ef97c56ff916.svg">
    <img alt="LHappyCureall's GitHub statistics: public repositories and community activity, commits in the last 365 days, private commits in that period, and commits in the last 30 days" src="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-light-6484ef97c56ff916.svg" width="860">
  </picture>
</a>

<sub>Commits (365 days): 167 · Of which private: 140 · Commits (30 days): 29 · Updated 2026-09-10 04:55 UTC.</sub>
<!-- PROFILE-STATS:END -->

<sub>Repository and community metrics use public data. Commit totals cover my authored commits on default branches of accessible owned repositories, including private repositories; only aggregate counts are published. [Scope and counting rules](./.github/PROFILE-STATS.md).</sub>

---

## 🔭 Research Interests
- Two-phase incompressible flow model
- Separate-Mass-Preserving Allen-Cahn-Navier-Stokes (SMP-ACNS) model
- Moving contact lines with generalized Navier boundary conditions（GNBC）
- Energy-stable & fully coupled fully-implicit FEM schemes
- Adaptive mesh refinement (AMR)
- Parallel nonlinear solvers (Newton-Krylov-Schwarz) on HPC platforms
- Nonlinear preconditioners such as nonlinear elimination (NE), nonlinear elimination preconditioned inexact Newton (NEPIN)
- Linear preconditioners such as two-level, constant two-level, linear elimination preconditioners

---

## 💻 Tech Stack
`C++` `PETSc` `libMesh` `Python` `MATLAB` `FreeFem++` `ParaView` `Tecplot` `COMSOL Multiphysics`
- **C++ / libMesh:** Finite element implementation and coupled-system assembly.
- **PETSc:** Nonlinear and linear solver integration using SNES and KSP.
- **ParaView / Tecplot:** Visualization and analysis of simulation results.
- **COMSOL Multiphysics** Familiarity with multiphysics model setup, meshing, and post-processing. 

---

## 🌱 Currently Working On
- Fully-coupled, second-order energy-stable schemes for two-phase flows with generalized Navier boundary conditions
- Large-scale simulations on Tianhe supercomputer
- Design a fully coupled, second-order numerical scheme with unconditional energy decay multiphase flow models with surfactants to simulate the impact of a drop on a substrate.

  ### ⚡ Selected Parallel Performance

A fixed-size strong-scaling experiment for the fully coupled SMP-ACNS solver:

- Degrees of freedom: 42,253,926
- Benchmark length: 5 time steps
- Time-step size: 0.01
- Solver configuration: Schwarz preconditioning, ILU(2), and GMRES restart 50
- Reported speedup and efficiency are relative to the 256 baseline

| Parallel size (`np`) | Nonlinear iteration | Linear iteration| Reported time (s) | Relative speedup | Parallel efficiency |
|---:| ---:|---:   | ---:   |---:  | ---:     |
256  | 3.0 | 17.60 | 128.45 | 1.00 | 100.00%  |
512  | 3.0 | 19.33 | 69.27  | 1.85 | 92.72%   |
1024 | 3.0 | 21.67 | 39.95  | 3.22 | 80.38%   |
2048 | 3.0 | 24.93 | 22.38  | 5.74 | 71.74%   |

These results describe strong scaling of the same solver on a fixed workload,
rather than a comparison against a different numerical algorithm.

---

## 📫 Contact
- Email: l18340091052@gmail.com
- Academic: yc37477@umac.mo
- Github: https://github.com/LHappyCureall

---

## 📊 Simulation Gallery
<!-- 这里放你的 gif 动画 -->
#### Milkcrown Re = 20
[![Re20](./gif/Re20.gif)](./Re20.mp4)

#### Milkcrown Re = 200
[![Re200](./gif/Re200.gif)](./Re200.mp4)

#### Milkcrown Re = 500
[![Re500](./gif/Re500.gif)](./Re500.mp4)

#### Milkcrown Re = 1000
[![Re1000](./gif/Re1000.gif)](./Re1000.mp4)

#### Milkcrown Re = 2000
[![Re1000](./gif/Re2000.gif)](./Re2000.mp4)

#### Droplet on a post solid surface 
[![post-real-y](./gif/post-real-y.gif)](./post-real-y.mp4)
[![post-real-z](./gif/post-real-z.gif)](./post-real-z.mp4)

#### Droplet impact simulations on sawtooth, wavy structures under different contact angles
[![post-60.gif](./gif/post-60.gif)](./post-60.mp4)
[![post-150.gif](./gif/post-150.gif)](./post-150.mp4)
[![sawtooth-60.gif](./gif/sawtooth-60.gif)](./sawtooth-60.mp4)
[![sawtooth-150.gif](./gif/sawtooth-150.gif)](./sawtooth-150.mp4)
[![wavy-60.gif](./gif/wavy-60.gif)](./wavy-60.mp4)
[![wavy-150.gif](./gif/wavy-150.gif)](./wavy-150.mp4)


#### Comparison of equilibrium profiles of clean (blue) and contaminated (red) droplets on different surfaces
[![0814-60theta.gif](./gif/0814-60theta.gif)](./gif/0814-60theta.gif)
[![0814-120theta.gif](./gif/0814-120theta.gif)](./gif/0814-120theta.gif)


