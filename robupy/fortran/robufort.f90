!*******************************************************************************
!*******************************************************************************
MODULE robufort_extension

    !/* external modules    */

    USE robufort_constants

    USE robufort_auxiliary

    !/* setup   */

    IMPLICIT NONE

    PUBLIC

CONTAINS
!*******************************************************************************
!*******************************************************************************
SUBROUTINE store_results(mapping_state_idx, states_all, periods_payoffs_ex_post, &
                periods_payoffs_systematic, states_number_period, periods_emax, &
                num_periods, min_idx) 

    !/* external objects    */

    INTEGER(our_int), INTENT(IN)    :: num_periods
    INTEGER(our_int), INTENT(IN)    :: min_idx 
    INTEGER(our_int), INTENT(IN)    :: mapping_state_idx(:, :, :, :, :)
    INTEGER(our_int), INTENT(IN)    :: states_all(:,:,:)
    INTEGER(our_int), INTENT(IN)    :: states_number_period(:)

    REAL(our_dble), INTENT(IN)      :: periods_payoffs_systematic(:, :, :)
    REAL(our_dble), INTENT(IN)      :: periods_payoffs_ex_post(:, :, :)    
    REAL(our_dble), INTENT(IN)      :: periods_emax(:, :)

    !/* internal objects    */

    INTEGER(our_int)                :: max_states_period
    INTEGER(our_int)                :: period
    INTEGER(our_int)                :: i
    INTEGER(our_int)                :: j
    INTEGER(our_int)                :: k

!-------------------------------------------------------------------------------
! Algorithm
!-------------------------------------------------------------------------------
    
    max_states_period = MAXVAL(states_number_period)


    1800 FORMAT(5(1x,i5))

    OPEN(UNIT=1, FILE='.mapping_state_idx.robufort.dat')

    DO period = 1, num_periods
        DO i = 1, num_periods
            DO j = 1, num_periods
                DO k = 1, min_idx
                    WRITE(1, 1800) mapping_state_idx(period, i, j, k, :)
                END DO
            END DO
        END DO
    END DO

    CLOSE(1)


    2000 FORMAT(4(1x,i5))

    OPEN(UNIT=1, FILE='.states_all.robufort.dat')

    DO period = 1, num_periods
        DO i = 1, max_states_period
            WRITE(1, 2000) states_all(period, i, :)
        END DO
    END DO

    CLOSE(1)


    1900 FORMAT(4(1x,f25.15))

    OPEN(UNIT=1, FILE='.periods_payoffs_systematic.robufort.dat')

    DO period = 1, num_periods
        DO i = 1, max_states_period
            WRITE(1, 1900) periods_payoffs_systematic(period, i, :)
        END DO
    END DO

    CLOSE(1)



    OPEN(UNIT=1, FILE='.periods_payoffs_ex_post.robufort.dat')

    DO period = 1, num_periods
        DO i = 1, max_states_period
            WRITE(1, 1900) periods_payoffs_ex_post(period, i, :)
        END DO
    END DO

    CLOSE(1)


    2100 FORMAT(i5)

    OPEN(UNIT=1, FILE='.states_number_period.robufort.dat')

    DO period = 1, num_periods
        WRITE(1, 2100) states_number_period(period)
    END DO

    CLOSE(1)


    2200 FORMAT(i5)

    OPEN(UNIT=1, FILE='.max_states_period.robufort.dat')

    WRITE(1, 2200) max_states_period

    CLOSE(1)


    2400 FORMAT(100000(1x,f25.15))

    OPEN(UNIT=1, FILE='.periods_emax.robufort.dat')

    DO period = 1, num_periods
        WRITE(1, 2400) periods_emax(period, :)
    END DO

    CLOSE(1)


END SUBROUTINE
!*******************************************************************************
!*******************************************************************************
SUBROUTINE read_specification(num_periods, delta, level, coeffs_a, coeffs_b, &
                coeffs_edu, edu_start, edu_max, coeffs_home, shocks, & 
                num_draws, seed_solution, num_agents, seed_simulation, & 
                is_debug, is_zero, is_interpolated, num_points, min_idx, & 
                is_ambiguous, measure) 

    !
    !   This function serves as the replacement for the clsRobupy and reads in 
    !   all required information about the model parameterization. It just 
    !   reads in all required information. No auxiliary processing is intended.
    !

    !/* external objects    */

    INTEGER(our_int), INTENT(OUT)   :: seed_simulation 
    INTEGER(our_int), INTENT(OUT)   :: seed_solution 
    INTEGER(our_int), INTENT(OUT)   :: num_periods
    INTEGER(our_int), INTENT(OUT)   :: num_agents
    INTEGER(our_int), INTENT(OUT)   :: num_points
    INTEGER(our_int), INTENT(OUT)   :: num_draws
    INTEGER(our_int), INTENT(OUT)   :: edu_start
    INTEGER(our_int), INTENT(OUT)   :: edu_max
    INTEGER(our_int), INTENT(OUT)   :: min_idx

    REAL(our_dble), INTENT(OUT)     :: coeffs_home(1)
    REAL(our_dble), INTENT(OUT)     :: coeffs_edu(3)
    REAL(our_dble), INTENT(OUT)     :: shocks(4, 4)
    REAL(our_dble), INTENT(OUT)     :: coeffs_a(6)
    REAL(our_dble), INTENT(OUT)     :: coeffs_b(6)
    REAL(our_dble), INTENT(OUT)     :: delta
    REAL(our_dble), INTENT(OUT)     :: level

    LOGICAL, INTENT(OUT)            :: is_interpolated
    LOGICAL, INTENT(OUT)            :: is_ambiguous    
    LOGICAL, INTENT(OUT)            :: is_debug
    LOGICAL, INTENT(OUT)            :: is_zero

    CHARACTER(10), INTENT(OUT)      :: measure 

    !/* internal objects    */

    INTEGER(our_int)                :: j
    INTEGER(our_int)                :: k

!-------------------------------------------------------------------------------
! Algorithm
!-------------------------------------------------------------------------------
    
    ! Fix formatting
    1500 FORMAT(6(1x,f15.10))
    1510 FORMAT(f15.10)

    1505 FORMAT(i10)
    1515 FORMAT(i10,1x,i10)

    !1520 FORMAT(15)

    ! Read model specification
    OPEN(UNIT=1, FILE='.model.robufort.ini')

        ! BASICS
        READ(1, 1505) num_periods
        READ(1, 1510) delta

        ! AMBIGUITY
        READ(1, 1510) level
        READ(1, *   ) measure

        ! WORK
        READ(1, 1500) coeffs_a
        READ(1, 1500) coeffs_b

        ! EDUCATION
        READ(1, 1500) coeffs_edu
        READ(1, 1515) edu_start, edu_max

        ! HOME
        READ(1, 1500) coeffs_home

        ! SHOCKS
        DO j = 1, 4
            READ(1, 1500) (shocks(j, k), k=1, 4)
        END DO

        ! SOLUTION
        READ(1, 1505) num_draws
        READ(1, 1505) seed_solution

        ! SIMULATION
        READ(1, 1505) num_agents
        READ(1, 1505) seed_simulation

        ! PROGRAM
        READ(1, *) is_debug

        ! INTERPOLATION
        READ(1, *) is_interpolated
        READ(1, 1505) num_points

        ! AUXILIARY
        READ(1, 1505) min_idx
        READ(1, *) is_ambiguous
        READ(1, *) is_zero

    CLOSE(1, STATUS='delete')

END SUBROUTINE
!*******************************************************************************
!*******************************************************************************
SUBROUTINE create_disturbances(periods_eps_relevant, shocks, seed, is_debug, & 
                is_zero, is_ambiguous) 

    !/* external objects    */

    REAL(our_dble), INTENT(INOUT)       :: periods_eps_relevant(:, :, :)

    REAL(our_dble), INTENT(IN)          :: shocks(4, 4)

    INTEGER(our_int),INTENT(IN)         :: seed 

    LOGICAL, INTENT(IN)                 :: is_ambiguous
    LOGICAL, INTENT(IN)                 :: is_debug
    LOGICAL, INTENT(IN)                 :: is_zero

    !/* internal objects    */

    REAL(our_dble)                      :: eps_cholesky(4, 4)

    INTEGER(our_int)                    :: seed_inflated(15)
    INTEGER(our_int)                    :: num_periods
    INTEGER(our_int)                    :: seed_size
    INTEGER(our_int)                    :: num_draws
    INTEGER(our_int)                    :: period
    INTEGER(our_int)                    :: j
    INTEGER(our_int)                    :: i
    
    LOGICAL                             :: READ_IN

!------------------------------------------------------------------------------- 
! Algorithm
!------------------------------------------------------------------------------- 

    ! Auxiliary objects
    num_periods = SIZE(periods_eps_relevant, 1)

    num_draws = SIZE(periods_eps_relevant, 2)

    CALL cholesky(eps_cholesky, shocks)

    ! Set random seed
    seed_inflated(:) = seed
    
    CALL RANDOM_SEED(size=seed_size)

    CALL RANDOM_SEED(put=seed_inflated)

    ! Create standard deviates
    INQUIRE(FILE='disturbances.txt', EXIST=READ_IN)

    IF ((READ_IN .EQV. .True.)  .AND. (is_debug .EQV. .True.)) THEN

        OPEN(12, file='disturbances.txt')

        DO period = 1, num_periods

            DO j = 1, num_draws
        
                2000 FORMAT(4(1x,f15.10))
                READ(12,2000) periods_eps_relevant(period, j, :)
        
            END DO
      
        END DO

        CLOSE(12)

    ELSE

        DO period = 1, num_periods

            CALL multivariate_normal(periods_eps_relevant(period, :, :))
        
        END DO

    END IF

    ! Transformations
    DO period = 1, num_periods
        
        ! Apply variance change
        DO i = 1, num_draws
        
            periods_eps_relevant(period, i:i, :) = &
                TRANSPOSE(MATMUL(eps_cholesky, TRANSPOSE(periods_eps_relevant(period, i:i, :))))
        
        END DO

    END DO

    ! Transformation in case of risk-only. In the case of ambiguity, this 
    ! transformation is later as it needs adjustment for the switched means.
    IF (.NOT. is_ambiguous) THEN
        
        ! Transform disturbance for occupations
        DO period = 1, num_periods

            DO j = 1, 2
            
                periods_eps_relevant(period, :, j) = &
                        EXP(periods_eps_relevant(period, :, j))
            
            END DO

        END DO
        
    END IF

    ! Special case of absence randomness (all disturbances equal to zero). Note
    ! that the disturbances for the two occupations are set to one instead of
    ! zero.
    IF (is_zero) THEN

        periods_eps_relevant = zero_dble

        DO period = 1, num_periods

            DO j = 1, 2

                periods_eps_relevant(period, :, j) = one_dble

            END DO

        END DO

    END IF

END SUBROUTINE
!******************************************************************************* 
!******************************************************************************* 
END MODULE 
!******************************************************************************* 
!******************************************************************************* 
PROGRAM robufort

    !/* external modules    */

    USE robufort_extension

    USE robufort_library

    !/* setup   */

    IMPLICIT NONE

    !/* objects */

    INTEGER(our_int), ALLOCATABLE   :: mapping_state_idx(:, :, :, :, :)
    INTEGER(our_int), ALLOCATABLE   :: states_number_period(:)
    INTEGER(our_int), ALLOCATABLE   :: states_all(:, :, :)

    INTEGER(our_int)                :: max_states_period
    INTEGER(our_int)                :: seed_simulation 
    INTEGER(our_int)                :: seed_solution 
    INTEGER(our_int)                :: num_periods
    INTEGER(our_int)                :: num_agents
    INTEGER(our_int)                :: num_points
    INTEGER(our_int)                :: edu_start
    INTEGER(our_int)                :: num_draws
    INTEGER(our_int)                :: edu_max
    INTEGER(our_int)                :: min_idx

    REAL(our_dble), ALLOCATABLE     :: periods_payoffs_systematic(:, :, :)
    REAL(our_dble), ALLOCATABLE     :: periods_payoffs_ex_post(:, :, :)
    REAL(our_dble), ALLOCATABLE     :: periods_future_payoffs(:, :, :)
    REAL(our_dble), ALLOCATABLE     :: periods_eps_relevant(:, :, :)
    REAL(our_dble), ALLOCATABLE     :: periods_emax(:, :)

    REAL(our_dble)                  :: coeffs_home(1)
    REAL(our_dble)                  :: coeffs_edu(3)
    REAL(our_dble)                  :: shocks(4, 4)
    REAL(our_dble)                  :: coeffs_a(6)
    REAL(our_dble)                  :: coeffs_b(6)
    REAL(our_dble)                  :: delta
    REAL(our_dble)                  :: level

    LOGICAL                         :: is_interpolated
    LOGICAL                         :: is_ambiguous
    LOGICAL                         :: is_debug
    LOGICAL                         :: is_zero

    CHARACTER(10)                   :: measure 

!-------------------------------------------------------------------------------
! Algorithm
!-------------------------------------------------------------------------------

    ! Read specification of model. This is the FORTRAN replacement for the 
    ! clsRobupy instance that carries the model parametrization for the 
    ! PYTHON/F2PY implementations.
    CALL read_specification(num_periods, delta, level, coeffs_a, coeffs_b, & 
            coeffs_edu, edu_start, edu_max, coeffs_home, shocks, num_draws, &
            seed_solution, num_agents, seed_simulation, is_debug, is_zero, &
            is_interpolated, num_points, min_idx, is_ambiguous, measure) 

    ! This part creates (or reads from disk) the disturbances for the Monte 
    ! Carlo integration of the EMAX. For is_debugging purposes, these might also be 
    ! read in from disk or set to zero/one.   
    ALLOCATE(periods_eps_relevant(num_periods, num_draws, 4))
    CALL create_disturbances(periods_eps_relevant, shocks, seed_solution, &
            is_debug, is_zero, is_ambiguous)

    ! Solve the model for a given parametrization.    
    CALL solve_fortran_bare(mapping_state_idx, periods_emax, & 
            periods_future_payoffs, periods_payoffs_ex_post, & 
            periods_payoffs_systematic, states_all, states_number_period, & 
            coeffs_a, coeffs_b, coeffs_edu, coeffs_home, shocks, edu_max, & 
            delta, edu_start, is_debug, is_interpolated, level, measure, & 
            min_idx, num_draws, num_periods, num_points, is_ambiguous, & 
            periods_eps_relevant)

    ! Store results. These are read in by the PYTHON wrapper and added to the 
    ! clsRobupy instance.
    CALL store_results(mapping_state_idx, states_all, periods_payoffs_ex_post, & 
            periods_payoffs_systematic, states_number_period, periods_emax, &
            num_periods, min_idx) 

!*******************************************************************************
!*******************************************************************************
END PROGRAM