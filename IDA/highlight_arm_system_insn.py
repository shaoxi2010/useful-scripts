# -*- coding: utf-8 -*-
#
# Script to highlight low-level instructions in ARM code.
# Automatically comment coprocessor accesses (MRC*/MCR*) with documentation.
#
# Support up to ARMv7-A / ARMv8 processors.
#
# Author: Guillaume Delugré.
#

from idc import *
from idautils import *
import idaapi

global current_arch
global summary_info

summary_info = {
    "Page table": set(),
    "Interrupt vectors": set(),
    "Return from interrupt": set(),
    "System calls": set(),
    "Cryptography": set(),
}

CRYPTO_INSN = (
    "AESE", "AESMC", "AESD",
    "BCAX", "EOR3", "RAX1", "XAR",
    "SHA1C", "SHA1H", "SHA1M", "SHA1P", "SHA1SU0", "SHA1SU1",
    "SHA256H2", "SHA256H", "SHA256SU0", "SHA256SU1",
    "SHA512H2", "SHA512H", "SHA512SU0", "SHA512SU1",
    "SM3PARTW1", "SM3PARTW2", "SM3SS1", "SM3TT1A", "SM3TT1B", "SM3TT2A", "SM3TT2B",
    "SM4E", "SM4EKEY"
)

SYSTEM_CALL_INSN = (
    "SVC", "SWI", "SMC", "SMI", "HVC"
)

SYSTEM_INSN = (
    # CPSR access
    "MSR", "MRS", "CPSIE", "CPSID",

    # CP access
    "MRC", "MRC2", "MRRC", "MRRC2", "MCR", "MCR2", "MCRR", "MCRR2", "LDC", "LDC2", "STC", "STC2", "CDP", "CDP2",

    # System (AArch64)
    "SYS", "SYSL", "IC", "DC", "AT", "TLBI",

    # Barriers,
    "DSB", "DMB", "ISB", "CLREX",

    # Misc
    "SRS", "VMRS", "VMSR", "DBG", "DCPS1", "DCPS2", "DCPS3", "DRPS",

    # Hints
    "YIELD", "WFE", "WFI", "SEV", "SEVL", "HINT"

    # Exceptions generating
    "BKPT", # AArch32
    "BRK",  # AArch64
    *SYSTEM_CALL_INSN,

    # Special modes
    "ENTERX", "LEAVEX", "BXJ"

    # Return from exception
    "RFE",  # Aarch32
    "ERET", # Aarch64

    # Pointer authentication
    "PACDA", "PACDZA", "PACDB", "PACDZB", "PACGA",
    "PACIA", "PACIA1716", "PACIASP", "PACIAZ", "PACIZA",
    "PACIB", "PACIB1716", "PACIBSP", "PACIBZ", "PACIZB",
    "AUTDA", "AUTDZA", "AUTDB", "AUTDZB",
    "AUTIA", "AUTIA1716", "AUTIASP", "AUTIAZ", "AUTIZA",
    "AUTIB", "AUTIB1716", "AUTIBSP", "AUTIBZ", "AUTIZB",

    # Crypto
    *CRYPTO_INSN
)

# 64 bits registers accessible from AArch32.
# Extracted from the XML specifications for v8.7-A (2021-06).
AARCH32_COPROC_REGISTERS_64 = {
        # MMU registers
        ( "p15", 0, "c2"  )           : ( "TTBR0", "Translation Table Base Register 0" ),
        ( "p15", 1, "c2"  )           : ( "TTBR1", "Translation Table Base Register 1" ),
        ( "p15", 6, "c2"  )           : ( "VTTBR", "Virtualization Translation Table Base Register" ),
        ( "p15", 4, "c2"  )           : ( "HTTBR", "Hyp Translation Table Base Register" ),
        ( "p15", 0, "c7"  )           : ( "PAR", "Physical Address Register" ),

        # Counters
        ( "p15", 0, "c9"  )           : ( "PMCCNTR", "Performance Monitors Cycle Count Register" ),
        ( "p15", 0, "c14" )           : ( "CNTPCT", "Counter-timer Physical Count register" ),
        ( "p15", 1, "c14" )           : ( "CNTVCT", "Counter-timer Virtual Count register" ),
        ( "p15", 2, "c14" )           : ( "CNTP_CVAL", "Counter-timer Physical Timer CompareValue register",
                                          "CNTHP_CVAL", "Counter-timer Hyp Physical CompareValue register",
                                          "CNTHPS_CVAL", "Counter-timer Secure Physical Timer CompareValue Register (EL2)" ),
        ( "p15", 3, "c14" )           : ( "CNTV_CVAL", "Counter-timer Virtual Timer CompareValue register",
                                          "CNTHV_CVAL", "Counter-timer Virtual Timer CompareValue register (EL2)",
                                          "CNTHVS_CVAL", "Counter-timer Secure Virtual Timer CompareValue Register (EL2)" ),
        ( "p15", 4, "c14" )           : ( "CNTVOFF", "Counter-timer Virtual Offset register" ),
        ( "p15", 6, "c14" )           : ( "CNTHP_CVAL", "Counter-timer Hyp Physical CompareValue register" ),
        ( "p15", 8, "c14" )           : ( "CNTPCTSS", "Counter-timer Self-Synchronized Physical Count register" ),
        ( "p15", 9, "c14" )           : ( "CNTVCTSS", "Counter-timer Self-Synchronized Virtual Count register" ),

        # CPU control/status registers.
        ( "p15", 0, "c15" )           : ( "CPUACTLR", "CPU Auxiliary Control Register" ),
        ( "p15", 1, "c15" )           : ( "CPUECTLR", "CPU Extended Control Register" ),
        ( "p15", 2, "c15" )           : ( "CPUMERRSR", "CPU Memory Error Syndrome Register" ),
        ( "p15", 3, "c15" )           : ( "L2MERRSR", "L2 Memory Error Syndrome Register" ),

        # Interrupts
        ( "p15", 0, "c12" )           : ( "ICC_SGI1R", "Interrupt Controller Software Generated Interrupt Group 1 Register" ),
        ( "p15", 1, "c12" )           : ( "ICC_ASGI1R", "Interrupt Controller Alias Software Generated Interrupt Group 1 Register" ),
        ( "p15", 2, "c12" )           : ( "ICC_SGI0R", "Interrupt Controller Software Generated Interrupt Group 0 Register" ),

        # Preload Engine operations
        ( "p15", 0, "c11" )           : ( "N/A", "Preload Engine Program New Channel operation" ),

        # Debug registers
        ( "p14", 0, "c1"  )           : ( "DBGDRAR", "Debug ROM Address Register" ),
        ( "p14", 0, "c2"  )           : ( "DBGDSAR", "Debug Self Address Register" ),

        # Activity monitors
        ( "p15", 0, "c0" )           : ( "AMEVCNTR00", "Activity Monitors Event Counter Registers 0" ),
        ( "p15", 1, "c0" )           : ( "AMEVCNTR01", "Activity Monitors Event Counter Registers 0" ),
        ( "p15", 2, "c0" )           : ( "AMEVCNTR02", "Activity Monitors Event Counter Registers 0" ),
        ( "p15", 3, "c0" )           : ( "AMEVCNTR03", "Activity Monitors Event Counter Registers 0" ),
        ( "p15", 0, "c2" )           : ( "AMEVCNTR10", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 1, "c2" )           : ( "AMEVCNTR11", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 2, "c2" )           : ( "AMEVCNTR12", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 3, "c2" )           : ( "AMEVCNTR13", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 4, "c2" )           : ( "AMEVCNTR14", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 5, "c2" )           : ( "AMEVCNTR15", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 6, "c2" )           : ( "AMEVCNTR16", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 7, "c2" )           : ( "AMEVCNTR17", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 0, "c3" )           : ( "AMEVCNTR18", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 1, "c3" )           : ( "AMEVCNTR19", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 2, "c3" )           : ( "AMEVCNTR110", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 3, "c3" )           : ( "AMEVCNTR111", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 4, "c3" )           : ( "AMEVCNTR112", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 5, "c3" )           : ( "AMEVCNTR113", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 6, "c3" )           : ( "AMEVCNTR114", "Activity Monitors Event Counter Registers 1" ),
        ( "p15", 7, "c3" )           : ( "AMEVCNTR115", "Activity Monitors Event Counter Registers 1" ),
}

# Extracted from the XML specifications for v8.7-A (2021-06).
AARCH32_COPROC_REGISTERS = {
        ( "p15", "c0", 0, "c0", 0 )   : ( "MIDR", "Main ID Register" ),
        ( "p15", "c0", 0, "c0", 1 )   : ( "CTR", "Cache Type Register" ),
        ( "p15", "c0", 0, "c0", 2 )   : ( "TCMTR", "TCM Type Register" ),
        ( "p15", "c0", 0, "c0", 3 )   : ( "TLBTR", "TLB Type Register" ),
        ( "p15", "c0", 0, "c0", 5 )   : ( "MPIDR", "Multiprocessor Affinity Register" ),
        ( "p15", "c0", 0, "c0", 6 )   : ( "REVIDR", "Revision ID Register" ),

        # Aliases
        ( "p15", "c0", 0, "c0", 4 )   : ( "MIDR", "Main ID Register" ),
        ( "p15", "c0", 0, "c0", 7 )   : ( "MIDR", "Main ID Register" ),

        # CPUID registers
        ( "p15", "c0", 0, "c1", 0 )   : ( "ID_PFR0", "Processor Feature Register 0" ),
        ( "p15", "c0", 0, "c1", 1 )   : ( "ID_PFR1", "Processor Feature Register 1" ),
        ( "p15", "c0", 0, "c3", 4 )   : ( "ID_PFR2", "Processor Feature Register 2" ),
        ( "p15", "c0", 0, "c1", 2 )   : ( "ID_DFR0", "Debug Feature Register 0" ),
        ( "p15", "c0", 0, "c1", 3 )   : ( "ID_AFR0", "Auxiliary Feature Register 0" ),
        ( "p15", "c0", 0, "c1", 4 )   : ( "ID_MMFR0", "Memory Model Feature Register 0" ),
        ( "p15", "c0", 0, "c1", 5 )   : ( "ID_MMFR1", "Memory Model Feature Register 1" ),
        ( "p15", "c0", 0, "c1", 6 )   : ( "ID_MMFR2", "Memory Model Feature Register 2" ),
        ( "p15", "c0", 0, "c1", 7 )   : ( "ID_MMFR3", "Memory Model Feature Register 3" ),
        ( "p15", "c0", 0, "c2", 6 )   : ( "ID_MMFR4", "Memory Model Feature Register 4" ),
        ( "p15", "c0", 0, "c3", 6 )   : ( "ID_MMFR5", "Memory Model Feature Register 5" ),
        ( "p15", "c0", 0, "c2", 0 )   : ( "ID_ISAR0", "Instruction Set Attribute Register 0" ),
        ( "p15", "c0", 0, "c2", 1 )   : ( "ID_ISAR1", "Instruction Set Attribute Register 1" ),
        ( "p15", "c0", 0, "c2", 2 )   : ( "ID_ISAR2", "Instruction Set Attribute Register 2" ),
        ( "p15", "c0", 0, "c2", 3 )   : ( "ID_ISAR3", "Instruction Set Attribute Register 3" ),
        ( "p15", "c0", 0, "c2", 4 )   : ( "ID_ISAR4", "Instruction Set Attribute Register 4" ),
        ( "p15", "c0", 0, "c2", 5 )   : ( "ID_ISAR5", "Instruction Set Attribute Register 5" ),
        ( "p15", "c0", 0, "c2", 7 )   : ( "ID_ISAR6", "Instruction Set Attribute Register 6" ),

        ( "p15", "c0", 1, "c0", 0 )   : ( "CCSIDR", "Current Cache Size ID Register" ),
        ( "p15", "c0", 1, "c0", 2 )   : ( "CCSIDR2", "Current Cache Size ID Register 2" ),
        ( "p15", "c0", 1, "c0", 1 )   : ( "CLIDR", "Cache Level ID Register" ),
        ( "p15", "c0", 1, "c0", 7 )   : ( "AIDR", "Auxiliary ID Register" ),
        ( "p15", "c0", 2, "c0", 0 )   : ( "CSSELR", "Cache Size Selection Register" ),
        ( "p15", "c0", 4, "c0", 0 )   : ( "VPIDR", "Virtualization Processor ID Register" ),
        ( "p15", "c0", 4, "c0", 5 )   : ( "VMPIDR", "Virtualization Multiprocessor ID Register" ),

        # System control registers
        ( "p15", "c1", 0, "c0", 0 )   : ( "SCTLR", "System Control Register" ),
        ( "p15", "c1", 0, "c0", 1 )   : ( "ACTLR", "Auxiliary Control Register" ),
        ( "p15", "c1", 0, "c0", 3 )   : ( "ACTLR2", "Auxiliary Control Register 2" ),
        ( "p15", "c1", 0, "c0", 2 )   : ( "CPACR", "Architectural Feature Access Control Register" ),
        ( "p15", "c1", 0, "c1", 0 )   : ( "SCR", "Secure Configuration Register" ),
        ( "p15", "c1", 0, "c1", 1 )   : ( "SDER", "Secure Debug Enable Register" ),
        ( "p15", "c1", 0, "c3", 1 )   : ( "SDCR", "Secure Debug Control Register" ),
        ( "p15", "c1", 0, "c1", 2 )   : ( "NSACR", "Non-Secure Access Control Register" ),
        ( "p15", "c1", 4, "c0", 0 )   : ( "HSCTLR", "Hyp System Control Register" ),
        ( "p15", "c1", 4, "c0", 1 )   : ( "HACTLR", "Hyp Auxiliary Control Register" ),
        ( "p15", "c1", 4, "c0", 3 )   : ( "HACTLR2", "Hyp Auxiliary Control Register 2" ),
        ( "p15", "c1", 4, "c1", 0 )   : ( "HCR", "Hyp Configuration Register" ),
        ( "p15", "c1", 4, "c1", 4 )   : ( "HCR2", "Hyp Configuration Register 2" ),
        ( "p15", "c1", 4, "c1", 1 )   : ( "HDCR", "Hyp Debug Control Register" ),
        ( "p15", "c1", 4, "c1", 2 )   : ( "HCPTR", "Hyp Architectural Feature Trap Register" ),
        ( "p15", "c1", 4, "c1", 3 )   : ( "HSTR", "Hyp System Trap Register" ),
        ( "p15", "c1", 4, "c1", 7 )   : ( "HACR", "Hyp Auxiliary Configuration Register" ),

        # Translation Table Base Registers
        ( "p15", "c2", 0, "c0", 0 )   : ( "TTBR0", "Translation Table Base Register 0" ),
        ( "p15", "c2", 0, "c0", 1 )   : ( "TTBR1", "Translation Table Base Register 1" ),
        ( "p15", "c2", 4, "c0", 2 )   : ( "HTCR", "Hyp Translation Control Register" ),
        ( "p15", "c2", 4, "c1", 2 )   : ( "VTCR", "Virtualization Translation Control Register" ),
        ( "p15", "c2", 0, "c0", 2 )   : ( "TTBCR", "Translation Table Base Control Register" ),
        ( "p15", "c2", 0, "c0", 3 )   : ( "TTBCR2", "Translation Table Base Control Register 2" ),

        # Domain Access Control registers
        ( "p15", "c3", 0, "c0", 0 )   : ( "DACR", "Domain Access Control Register" ),

        # Fault Status registers
        ( "p15", "c5", 0, "c0", 0 )   : ( "DFSR", "Data Fault Status Register" ),
        ( "p15", "c5", 0, "c0", 1 )   : ( "IFSR", "Instruction Fault Status Register" ),
        ( "p15", "c5", 0, "c1", 0 )   : ( "ADFSR", "Auxiliary Data Fault Status Register" ),
        ( "p15", "c5", 0, "c1", 1 )   : ( "AIFSR", "Auxiliary Instruction Fault Status Register" ),
        ( "p15", "c5", 4, "c1", 0 )   : ( "HADFSR", "Hyp Auxiliary Data Fault Status Register" ),
        ( "p15", "c5", 4, "c1", 1 )   : ( "HAIFSR", "Hyp Auxiliary Instruction Fault Status Register" ),
        ( "p15", "c5", 4, "c2", 0 )   : ( "HSR", "Hyp Syndrome Register" ),

        # Fault Address registers
        ( "p15", "c6", 0, "c0", 0 )   : ( "DFAR", "Data Fault Address Register" ),
        ( "p15", "c6", 0, "c0", 1 )   : ( "N/A", "Watchpoint Fault Address" ), # ARM11
        ( "p15", "c6", 0, "c0", 2 )   : ( "IFAR", "Instruction Fault Address Register" ),
        ( "p15", "c6", 4, "c0", 0 )   : ( "HDFAR", "Hyp Data Fault Address Register" ),
        ( "p15", "c6", 4, "c0", 2 )   : ( "HIFAR", "Hyp Instruction Fault Address Register" ),
        ( "p15", "c6", 4, "c0", 4 )   : ( "HPFAR", "Hyp IPA Fault Address Register" ),

        # Cache maintenance registers
        ( "p15", "c7", 0, "c0", 4 )   : ( "NOP", "No Operation / Wait For Interrupt" ),
        ( "p15", "c7", 0, "c1", 0 )   : ( "ICIALLUIS", "Instruction Cache Invalidate All to PoU, Inner Shareable" ),
        ( "p15", "c7", 0, "c1", 6 )   : ( "BPIALLIS", "Branch Predictor Invalidate All, Inner Shareable" ),
        ( "p15", "c7", 0, "c4", 0 )   : ( "PAR", "Physical Address Register" ),
        ( "p15", "c7", 0, "c5", 0 )   : ( "ICIALLU", "Instruction Cache Invalidate All to PoU" ),
        ( "p15", "c7", 0, "c5", 1 )   : ( "ICIMVAU", "Instruction Cache line Invalidate by VA to PoU" ),
        ( "p15", "c7", 0, "c5", 2 )   : ( "N/A", "Invalidate all instruction caches by set/way" ), # ARM11
        ( "p15", "c7", 0, "c5", 4 )   : ( "CP15ISB", "Instruction Synchronization Barrier System instruction" ),
        ( "p15", "c7", 0, "c5", 6 )   : ( "BPIALL", "Branch Predictor Invalidate All" ),
        ( "p15", "c7", 0, "c5", 7 )   : ( "BPIMVA", "Branch Predictor Invalidate by VA" ),
        ( "p15", "c7", 0, "c6", 0 )   : ( "N/A", "Invalidate entire data cache" ),
        ( "p15", "c7", 0, "c6", 1 )   : ( "DCIMVAC", "Data Cache line Invalidate by VA to PoC" ),
        ( "p15", "c7", 0, "c6", 2 )   : ( "DCISW", "Data Cache line Invalidate by Set/Way" ),
        ( "p15", "c7", 0, "c7", 0 )   : ( "N/A", "Invalidate instruction cache and data cache" ), # ARM11
        ( "p15", "c7", 0, "c8", 0 )   : ( "ATS1CPR", "Address Translate Stage 1 Current state PL1 Read" ),
        ( "p15", "c7", 0, "c8", 1 )   : ( "ATS1CPW", "Address Translate Stage 1 Current state PL1 Write" ),
        ( "p15", "c7", 0, "c8", 2 )   : ( "ATS1CUR", "Address Translate Stage 1 Current state Unprivileged Read" ),
        ( "p15", "c7", 0, "c8", 3 )   : ( "ATS1CUW", "Address Translate Stage 1 Current state Unprivileged Write" ),
        ( "p15", "c7", 0, "c8", 4 )   : ( "ATS12NSOPR", "Address Translate Stages 1 and 2 Non-secure Only PL1 Read" ),
        ( "p15", "c7", 0, "c8", 5 )   : ( "ATS12NSOPW", "Address Translate Stages 1 and 2 Non-secure Only PL1 Write" ),
        ( "p15", "c7", 0, "c8", 6 )   : ( "ATS12NSOUR", "Address Translate Stages 1 and 2 Non-secure Only Unprivileged Read" ),
        ( "p15", "c7", 0, "c8", 7 )   : ( "ATS12NSOUW", "Address Translate Stages 1 and 2 Non-secure Only Unprivileged Write" ),
        ( "p15", "c7", 0, "c9", 0 )   : ( "ATS1CPRP", "Address Translate Stage 1 Current state PL1 Read PAN" ),
        ( "p15", "c7", 0, "c9", 1 )   : ( "ATS1CPWP", "Address Translate Stage 1 Current state PL1 Write PAN" ),
        ( "p15", "c7", 0, "c10", 0 )  : ( "N/A", "Clean entire data cache" ), # ARM11
        ( "p15", "c7", 0, "c10", 1 )  : ( "DCCMVAC", "Data Cache line Clean by VA to PoC" ),
        ( "p15", "c7", 0, "c10", 2 )  : ( "DCCSW", "Data Cache line Clean by Set/Way" ),
        ( "p15", "c7", 0, "c10", 3 )  : ( "N/A", "Test and clean data cache" ), # ARM9
        ( "p15", "c7", 0, "c10", 4 )  : ( "CP15DSB", "Data Synchronization Barrier System instruction" ),
        ( "p15", "c7", 0, "c10", 5 )  : ( "CP15DMB", "Data Memory Barrier System instruction" ),
        ( "p15", "c7", 0, "c10", 6 )  : ( "N/A", "Read Cache Dirty Status Register" ), # ARM11
        ( "p15", "c7", 0, "c11", 1 )  : ( "DCCMVAU", "Data Cache line Clean by VA to PoU" ),
        ( "p15", "c7", 0, "c12", 4 )  : ( "N/A", "Read Block Transfer Status Register" ), # ARM11
        ( "p15", "c7", 0, "c12", 5 )  : ( "N/A", "Stop Prefetch Range" ), # ARM11
        ( "p15", "c7", 0, "c13", 1 )  : ( "NOP", "No Operation / Prefetch Instruction Cache Line" ),
        ( "p15", "c7", 0, "c14", 0 )  : ( "N/A", "Clean and invalidate entire data cache" ), # ARM11
        ( "p15", "c7", 0, "c14", 1 )  : ( "DCCIMVAC", "Data Cache line Clean and Invalidate by VA to PoC" ),
        ( "p15", "c7", 0, "c14", 2 )  : ( "DCCISW", "Data Cache line Clean and Invalidate by Set/Way" ),
        ( "p15", "c7", 0, "c14", 3 )  : ( "N/A", "Test, clean, and invalidate data cache" ), # ARM9
        ( "p15", "c7", 4, "c8", 0 )   : ( "ATS1HR", "Address Translate Stage 1 Hyp mode Read" ),
        ( "p15", "c7", 4, "c8", 1 )   : ( "ATS1HW", "Stage 1 Hyp mode write" ),

        # TLB maintenance operations
        ( "p15", "c8", 0, "c3", 0 )   : ( "TLBIALLIS", "TLB Invalidate All, Inner Shareable" ),
        ( "p15", "c8", 0, "c3", 1 )   : ( "TLBIMVAIS", "TLB Invalidate by VA, Inner Shareable" ),
        ( "p15", "c8", 0, "c3", 2 )   : ( "TLBIASIDIS", "TLB Invalidate by ASID match, Inner Shareable" ),
        ( "p15", "c8", 0, "c3", 3 )   : ( "TLBIMVAAIS", "TLB Invalidate by VA, All ASID, Inner Shareable" ),
        ( "p15", "c8", 0, "c3", 5 )   : ( "TLBIMVALIS", "TLB Invalidate by VA, Last level, Inner Shareable" ),
        ( "p15", "c8", 0, "c3", 7 )   : ( "TLBIMVAALIS", "TLB Invalidate by VA, All ASID, Last level, Inner Shareable" ),
        ( "p15", "c8", 0, "c5", 0 )   : ( "ITLBIALL", "Instruction TLB Invalidate All" ),
        ( "p15", "c8", 0, "c5", 1 )   : ( "ITLBIMVA", "Instruction TLB Invalidate by VA" ),
        ( "p15", "c8", 0, "c5", 2 )   : ( "ITLBIASID", "Instruction TLB Invalidate by ASID match" ),
        ( "p15", "c8", 0, "c6", 0 )   : ( "DTLBIALL", "Data TLB Invalidate All" ),
        ( "p15", "c8", 0, "c6", 1 )   : ( "DTLBIMVA", "Data TLB Invalidate by VA" ),
        ( "p15", "c8", 0, "c6", 2 )   : ( "DTLBIASID", "Data TLB Invalidate by ASID match" ),
        ( "p15", "c8", 0, "c7", 0 )   : ( "TLBIALL", "TLB Invalidate All" ),
        ( "p15", "c8", 0, "c7", 1 )   : ( "TLBIMVA", "TLB Invalidate by VA" ),
        ( "p15", "c8", 0, "c7", 2 )   : ( "TLBIASID", "TLB Invalidate by ASID match" ),
        ( "p15", "c8", 0, "c7", 3 )   : ( "TLBIMVAA", "TLB Invalidate by VA, All ASID" ),
        ( "p15", "c8", 0, "c7", 5 )   : ( "TLBIMVAL", "TLB Invalidate by VA, Last level" ),
        ( "p15", "c8", 0, "c7", 7 )   : ( "TLBIMVAAL", "TLB Invalidate by VA, All ASID, Last level" ),
        ( "p15", "c8", 4, "c0", 1 )   : ( "TLBIIPAS2IS", "TLB Invalidate by Intermediate Physical Address, Stage 2, Inner Shareable" ),
        ( "p15", "c8", 4, "c0", 5 )   : ( "TLBIIPAS2LIS", "TLB Invalidate by Intermediate Physical Address, Stage 2, Last level, Inner Shareable" ),
        ( "p15", "c8", 4, "c3", 0 )   : ( "TLBIALLHIS", "TLB Invalidate All, Hyp mode, Inner Shareable" ),
        ( "p15", "c8", 4, "c3", 1 )   : ( "TLBIMVAHIS", "TLB Invalidate by VA, Hyp mode, Inner Shareable" ),
        ( "p15", "c8", 4, "c3", 4 )   : ( "TLBIALLNSNHIS", "TLB Invalidate All, Non-Secure Non-Hyp, Inner Shareable" ),
        ( "p15", "c8", 4, "c3", 5 )   : ( "TLBIMVALHIS", "TLB Invalidate by VA, Last level, Hyp mode, Inner Shareable" ),
        ( "p15", "c8", 4, "c4", 1 )   : ( "TLBIIPAS2", "TLB Invalidate by Intermediate Physical Address, Stage 2" ),
        ( "p15", "c8", 4, "c4", 5 )   : ( "TLBIIPAS2L", "TLB Invalidate by Intermediate Physical Address, Stage 2, Last level" ),
        ( "p15", "c8", 4, "c7", 0 )   : ( "TLBIALLH", "TLB Invalidate All, Hyp mode" ),
        ( "p15", "c8", 4, "c7", 1 )   : ( "TLBIMVAH", "TLB Invalidate by VA, Hyp mode" ),
        ( "p15", "c8", 4, "c7", 4 )   : ( "TLBIALLNSNH", "TLB Invalidate All, Non-Secure Non-Hyp" ),
        ( "p15", "c8", 4, "c7", 5 )   : ( "TLBIMVALH", "TLB Invalidate by VA, Last level, Hyp mode" ),

        ( "p15", "c9", 0, "c0", 0 )   : ( "N/A", "Data Cache Lockdown" ), # ARM11
        ( "p15", "c9", 0, "c0", 1 )   : ( "N/A", "Instruction Cache Lockdown" ), # ARM11
        ( "p15", "c9", 0, "c1", 0 )   : ( "N/A", "Data TCM Region" ), # ARM11
        ( "p15", "c9", 0, "c1", 1 )   : ( "N/A", "Instruction TCM Region" ), # ARM11
        ( "p15", "c9", 1, "c0", 2 )   : ( "L2CTLR", "L2 Control Register" ),
        ( "p15", "c9", 1, "c0", 3 )   : ( "L2ECTLR", "L2 Extended Control Register" ),

        # Performance monitor registers
        ( "p15", "c9", 0, "c12", 0 )  : ( "PMCR", "Performance Monitors Control Register" ),
        ( "p15", "c9", 0, "c12", 1)   : ( "PMCNTENSET", "Performance Monitor Count Enable Set Register" ),
        ( "p15", "c9", 0, "c12", 2)   : ( "PMCNTENCLR", "Performance Monitor Control Enable Clear Register" ),
        ( "p15", "c9", 0, "c12", 3 )  : ( "PMOVSR", "Performance Monitors Overflow Flag Status Register" ),
        ( "p15", "c9", 0, "c12", 4 )  : ( "PMSWINC", "Performance Monitors Software Increment register" ),
        ( "p15", "c9", 0, "c12", 5 )  : ( "PMSELR", "Performance Monitors Event Counter Selection Register" ),
        ( "p15", "c9", 0, "c12", 6 )  : ( "PMCEID0", "Performance Monitors Common Event Identification register 0" ),
        ( "p15", "c9", 0, "c12", 7 )  : ( "PMCEID1", "Performance Monitors Common Event Identification register 1" ),
        ( "p15", "c9", 0, "c13", 0 )  : ( "PMCCNTR", "Performance Monitors Cycle Count Register" ),
        ( "p15", "c9", 0, "c13", 1 )  : ( "PMXEVTYPER", "Performance Monitors Selected Event Type Register" ),
        ( "p15", "c9", 0, "c13", 2 )  : ( "PMXEVCNTR", "Performance Monitors Selected Event Count Register" ),
        ( "p15", "c9", 0, "c14", 0 )  : ( "PMUSERENR", "Performance Monitors User Enable Register" ),
        ( "p15", "c9", 0, "c14", 1 )  : ( "PMINTENSET", "Performance Monitors Interrupt Enable Set register" ),
        ( "p15", "c9", 0, "c14", 2 )  : ( "PMINTENCLR", "Performance Monitors Interrupt Enable Clear register" ),
        ( "p15", "c9", 0, "c14", 3 )  : ( "PMOVSSET", "Performance Monitors Overflow Flag Status Set register" ),
        ( "p15", "c9", 0, "c14", 4 )  : ( "PMCEID2", "Performance Monitors Common Event Identification register 2" ),
        ( "p15", "c9", 0, "c14", 5 )  : ( "PMCEID3", "Performance Monitors Common Event Identification register 3" ),
        ( "p15", "c9", 0, "c14", 6 )  : ( "PMMIR", "Performance Monitors Machine Identification Register" ),
        ( "p15", "c14", 0, "c8", 0 )  : ( "PMEVCNTR0", "Performance Monitors Event Count Register 0" ),
        ( "p15", "c14", 0, "c8", 1 )  : ( "PMEVCNTR1", "Performance Monitors Event Count Register 1" ),
        ( "p15", "c14", 0, "c8", 2 )  : ( "PMEVCNTR2", "Performance Monitors Event Count Register 2" ),
        ( "p15", "c14", 0, "c8", 3 )  : ( "PMEVCNTR3", "Performance Monitors Event Count Register 3" ),
        ( "p15", "c14", 0, "c8", 4 )  : ( "PMEVCNTR4", "Performance Monitors Event Count Register 4" ),
        ( "p15", "c14", 0, "c8", 5 )  : ( "PMEVCNTR5", "Performance Monitors Event Count Register 5" ),
        ( "p15", "c14", 0, "c8", 6 )  : ( "PMEVCNTR6", "Performance Monitors Event Count Register 6" ),
        ( "p15", "c14", 0, "c8", 7 )  : ( "PMEVCNTR7", "Performance Monitors Event Count Register 7" ),
        ( "p15", "c14", 0, "c9", 0 )  : ( "PMEVCNTR8", "Performance Monitors Event Count Register 8" ),
        ( "p15", "c14", 0, "c9", 1 )  : ( "PMEVCNTR9", "Performance Monitors Event Count Register 9" ),
        ( "p15", "c14", 0, "c9", 2 )  : ( "PMEVCNTR10", "Performance Monitors Event Count Register 10" ),
        ( "p15", "c14", 0, "c9", 3 )  : ( "PMEVCNTR11", "Performance Monitors Event Count Register 11" ),
        ( "p15", "c14", 0, "c9", 4 )  : ( "PMEVCNTR12", "Performance Monitors Event Count Register 12" ),
        ( "p15", "c14", 0, "c9", 5 )  : ( "PMEVCNTR13", "Performance Monitors Event Count Register 13" ),
        ( "p15", "c14", 0, "c9", 6 )  : ( "PMEVCNTR14", "Performance Monitors Event Count Register 14" ),
        ( "p15", "c14", 0, "c9", 7 )  : ( "PMEVCNTR15", "Performance Monitors Event Count Register 15" ),
        ( "p15", "c14", 0, "c10", 0 ) : ( "PMEVCNTR16", "Performance Monitors Event Count Register 16" ),
        ( "p15", "c14", 0, "c10", 1 ) : ( "PMEVCNTR17", "Performance Monitors Event Count Register 17" ),
        ( "p15", "c14", 0, "c10", 2 ) : ( "PMEVCNTR18", "Performance Monitors Event Count Register 18" ),
        ( "p15", "c14", 0, "c10", 3 ) : ( "PMEVCNTR19", "Performance Monitors Event Count Register 19" ),
        ( "p15", "c14", 0, "c10", 4 ) : ( "PMEVCNTR20", "Performance Monitors Event Count Register 20" ),
        ( "p15", "c14", 0, "c10", 5 ) : ( "PMEVCNTR21", "Performance Monitors Event Count Register 21" ),
        ( "p15", "c14", 0, "c10", 6 ) : ( "PMEVCNTR22", "Performance Monitors Event Count Register 22" ),
        ( "p15", "c14", 0, "c10", 7 ) : ( "PMEVCNTR23", "Performance Monitors Event Count Register 23" ),
        ( "p15", "c14", 0, "c11", 0 ) : ( "PMEVCNTR24", "Performance Monitors Event Count Register 24" ),
        ( "p15", "c14", 0, "c11", 1 ) : ( "PMEVCNTR25", "Performance Monitors Event Count Register 25" ),
        ( "p15", "c14", 0, "c11", 2 ) : ( "PMEVCNTR26", "Performance Monitors Event Count Register 26" ),
        ( "p15", "c14", 0, "c11", 3 ) : ( "PMEVCNTR27", "Performance Monitors Event Count Register 27" ),
        ( "p15", "c14", 0, "c11", 4 ) : ( "PMEVCNTR28", "Performance Monitors Event Count Register 28" ),
        ( "p15", "c14", 0, "c11", 5 ) : ( "PMEVCNTR29", "Performance Monitors Event Count Register 29" ),
        ( "p15", "c14", 0, "c11", 6 ) : ( "PMEVCNTR30", "Performance Monitors Event Count Register 30" ),
        ( "p15", "c14", 0, "c12", 0 ) : ( "PMEVTYPER0", "Performance Monitors Event Type Register 0" ),
        ( "p15", "c14", 0, "c12", 1 ) : ( "PMEVTYPER1", "Performance Monitors Event Type Register 1" ),
        ( "p15", "c14", 0, "c12", 2 ) : ( "PMEVTYPER2", "Performance Monitors Event Type Register 2" ),
        ( "p15", "c14", 0, "c12", 3 ) : ( "PMEVTYPER3", "Performance Monitors Event Type Register 3" ),
        ( "p15", "c14", 0, "c12", 4 ) : ( "PMEVTYPER4", "Performance Monitors Event Type Register 4" ),
        ( "p15", "c14", 0, "c12", 5 ) : ( "PMEVTYPER5", "Performance Monitors Event Type Register 5" ),
        ( "p15", "c14", 0, "c12", 6 ) : ( "PMEVTYPER6", "Performance Monitors Event Type Register 6" ),
        ( "p15", "c14", 0, "c12", 7 ) : ( "PMEVTYPER7", "Performance Monitors Event Type Register 7" ),
        ( "p15", "c14", 0, "c13", 0 ) : ( "PMEVTYPER8", "Performance Monitors Event Type Register 8" ),
        ( "p15", "c14", 0, "c13", 1 ) : ( "PMEVTYPER9", "Performance Monitors Event Type Register 9" ),
        ( "p15", "c14", 0, "c13", 2 ) : ( "PMEVTYPER10", "Performance Monitors Event Type Register 10" ),
        ( "p15", "c14", 0, "c13", 3 ) : ( "PMEVTYPER11", "Performance Monitors Event Type Register 11" ),
        ( "p15", "c14", 0, "c13", 4 ) : ( "PMEVTYPER12", "Performance Monitors Event Type Register 12" ),
        ( "p15", "c14", 0, "c13", 5 ) : ( "PMEVTYPER13", "Performance Monitors Event Type Register 13" ),
        ( "p15", "c14", 0, "c13", 6 ) : ( "PMEVTYPER14", "Performance Monitors Event Type Register 14" ),
        ( "p15", "c14", 0, "c13", 7 ) : ( "PMEVTYPER15", "Performance Monitors Event Type Register 15" ),
        ( "p15", "c14", 0, "c14", 0 ) : ( "PMEVTYPER16", "Performance Monitors Event Type Register 16" ),
        ( "p15", "c14", 0, "c14", 1 ) : ( "PMEVTYPER17", "Performance Monitors Event Type Register 17" ),
        ( "p15", "c14", 0, "c14", 2 ) : ( "PMEVTYPER18", "Performance Monitors Event Type Register 18" ),
        ( "p15", "c14", 0, "c14", 3 ) : ( "PMEVTYPER19", "Performance Monitors Event Type Register 19" ),
        ( "p15", "c14", 0, "c14", 4 ) : ( "PMEVTYPER20", "Performance Monitors Event Type Register 20" ),
        ( "p15", "c14", 0, "c14", 5 ) : ( "PMEVTYPER21", "Performance Monitors Event Type Register 21" ),
        ( "p15", "c14", 0, "c14", 6 ) : ( "PMEVTYPER22", "Performance Monitors Event Type Register 22" ),
        ( "p15", "c14", 0, "c14", 7 ) : ( "PMEVTYPER23", "Performance Monitors Event Type Register 23" ),
        ( "p15", "c14", 0, "c15", 0 ) : ( "PMEVTYPER24", "Performance Monitors Event Type Register 24" ),
        ( "p15", "c14", 0, "c15", 1 ) : ( "PMEVTYPER25", "Performance Monitors Event Type Register 25" ),
        ( "p15", "c14", 0, "c15", 2 ) : ( "PMEVTYPER26", "Performance Monitors Event Type Register 26" ),
        ( "p15", "c14", 0, "c15", 3 ) : ( "PMEVTYPER27", "Performance Monitors Event Type Register 27" ),
        ( "p15", "c14", 0, "c15", 4 ) : ( "PMEVTYPER28", "Performance Monitors Event Type Register 28" ),
        ( "p15", "c14", 0, "c15", 5 ) : ( "PMEVTYPER29", "Performance Monitors Event Type Register 29" ),
        ( "p15", "c14", 0, "c15", 6 ) : ( "PMEVTYPER30", "Performance Monitors Event Type Register 30" ),
        ( "p15", "c14", 0, "c15", 7 ) : ( "PMCCFILTR", "Performance Monitors Cycle Count Filter Register" ),

        # Activity Monitors
        ( "p15", "c13", 0, "c2", 1 )  : ( "AMCFGR", "Activity Monitors Configuration Register" ),
        ( "p15", "c13", 0, "c2", 2 )  : ( "AMCGCR", "Activity Monitors Counter Group Configuration Register" ),
        ( "p15", "c13", 0, "c2", 4 )  : ( "AMCNTENCLR0", "Activity Monitors Count Enable Clear Register 0" ),
        ( "p15", "c13", 0, "c3", 0 )  : ( "AMCNTENCLR1", "Activity Monitors Count Enable Clear Register 1" ),
        ( "p15", "c13", 0, "c2", 5 )  : ( "AMCNTENSET0", "Activity Monitors Count Enable Set Register 0" ),
        ( "p15", "c13", 0, "c3", 1 )  : ( "AMCNTENSET1", "Activity Monitors Count Enable Set Register 1" ),
        ( "p15", "c13", 0, "c2", 0 )  : ( "AMCR", "Activity Monitors Control Register" ),
        ( "p15", "c13", 0, "c6", 0 )  : ( "AMEVTYPER00", "Activity Monitors Event Type Registers 0" ),
        ( "p15", "c13", 0, "c6", 1 )  : ( "AMEVTYPER01", "Activity Monitors Event Type Registers 0" ),
        ( "p15", "c13", 0, "c6", 2 )  : ( "AMEVTYPER02", "Activity Monitors Event Type Registers 0" ),
        ( "p15", "c13", 0, "c14", 0 ) : ( "AMEVTYPER10", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 1 ) : ( "AMEVTYPER11", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 2 ) : ( "AMEVTYPER12", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 3 ) : ( "AMEVTYPER13", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 4 ) : ( "AMEVTYPER14", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 5 ) : ( "AMEVTYPER15", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 6 ) : ( "AMEVTYPER16", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c14", 7 ) : ( "AMEVTYPER17", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 0 ) : ( "AMEVTYPER18", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 1 ) : ( "AMEVTYPER19", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 2 ) : ( "AMEVTYPER110", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 3 ) : ( "AMEVTYPER111", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 4 ) : ( "AMEVTYPER112", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 5 ) : ( "AMEVTYPER113", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c15", 6 ) : ( "AMEVTYPER114", "Activity Monitors Event Type Registers 1" ),
        ( "p15", "c13", 0, "c2", 3 )  : ( "AMUSERENR", "Activity Monitors User Enable Register" ),

        # Reliability
        ( "p15", "c12", 0, "c1", 1 )  : ( "DISR", "Deferred Interrupt Status Register" ),
        ( "p15", "c5", 0, "c3", 0 )   : ( "ERRIDR", "Error Record ID Register" ),
        ( "p15", "c5", 0, "c3", 1 )   : ( "ERRSELR", "Error Record Select Register" ),
        ( "p15", "c5", 0, "c4", 3 )   : ( "ERXADDR", "Selected Error Record Address Register" ),
        ( "p15", "c5", 0, "c4", 7 )   : ( "ERXADDR2", "Selected Error Record Address Register 2" ),
        ( "p15", "c5", 0, "c4", 1 )   : ( "ERXCTLR", "Selected Error Record Control Register" ),
        ( "p15", "c5", 0, "c4", 5 )   : ( "ERXCTLR2", "Selected Error Record Control Register 2" ),
        ( "p15", "c5", 0, "c4", 0 )   : ( "ERXFR", "Selected Error Record Feature Register" ),
        ( "p15", "c5", 0, "c4", 4 )   : ( "ERXFR2", "Selected Error Record Feature Register 2" ),
        ( "p15", "c5", 0, "c5", 0 )   : ( "ERXMISC0", "Selected Error Record Miscellaneous Register 0" ),
        ( "p15", "c5", 0, "c5", 1 )   : ( "ERXMISC1", "Selected Error Record Miscellaneous Register 1" ),
        ( "p15", "c5", 0, "c5", 4 )   : ( "ERXMISC2", "Selected Error Record Miscellaneous Register 2" ),
        ( "p15", "c5", 0, "c5", 5 )   : ( "ERXMISC3", "Selected Error Record Miscellaneous Register 3" ),
        ( "p15", "c5", 0, "c5", 2 )   : ( "ERXMISC4", "Selected Error Record Miscellaneous Register 4" ),
        ( "p15", "c5", 0, "c5", 3 )   : ( "ERXMISC5", "Selected Error Record Miscellaneous Register 5" ),
        ( "p15", "c5", 0, "c5", 6 )   : ( "ERXMISC6", "Selected Error Record Miscellaneous Register 6" ),
        ( "p15", "c5", 0, "c5", 7 )   : ( "ERXMISC7", "Selected Error Record Miscellaneous Register 7" ),
        ( "p15", "c5", 0, "c4", 2 )   : ( "ERXSTATUS", "Selected Error Record Primary Status Register" ),
        ( "p15", "c5", 4, "c2", 3 )   : ( "VDFSR", "Virtual SError Exception Syndrome Register" ),
        ( "p15", "c12", 4, "c1", 1 )   : ( "VDISR", "Virtual Deferred Interrupt Status Register" ),

        # Memory attribute registers
        ( "p15", "c10", 0, "c0", 0 )  : ( "N/A", "TLB Lockdown" ), # ARM11
        ( "p15", "c10", 0, "c2", 0 )  : ( "MAIR0", "Memory Attribute Indirection Register 0", "PRRR", "Primary Region Remap Register" ),
        ( "p15", "c10", 0, "c2", 1 )  : ( "MAIR1", "Memory Attribute Indirection Register 1", "NMRR", "Normal Memory Remap Register" ),
        ( "p15", "c10", 0, "c3", 0 )  : ( "AMAIR0", "Auxiliary Memory Attribute Indirection Register 0" ),
        ( "p15", "c10", 0, "c3", 1 )  : ( "AMAIR1", "Auxiliary Memory Attribute Indirection Register 1" ),
        ( "p15", "c10", 4, "c2", 0 )  : ( "HMAIR0", "Hyp Memory Attribute Indirection Register 0" ),
        ( "p15", "c10", 4, "c2", 1 )  : ( "HMAIR1", "Hyp Memory Attribute Indirection Register 1" ),
        ( "p15", "c10", 4, "c3", 0 )  : ( "HAMAIR0", "Hyp Auxiliary Memory Attribute Indirection Register 0" ),
        ( "p15", "c10", 4, "c3", 1 )  : ( "HAMAIR1", "Hyp Auxiliary Memory Attribute Indirection Register 1" ),

        # DMA registers (ARM11)
        ( "p15", "c11", 0, "c0", 0 )  : ( "N/A", "DMA Identification and Status (Present)" ),
        ( "p15", "c11", 0, "c0", 1 )  : ( "N/A", "DMA Identification and Status (Queued)" ),
        ( "p15", "c11", 0, "c0", 2 )  : ( "N/A", "DMA Identification and Status (Running)" ),
        ( "p15", "c11", 0, "c0", 3 )  : ( "N/A", "DMA Identification and Status (Interrupting)" ),
        ( "p15", "c11", 0, "c1", 0 )  : ( "N/A", "DMA User Accessibility" ),
        ( "p15", "c11", 0, "c2", 0 )  : ( "N/A", "DMA Channel Number" ),
        ( "p15", "c11", 0, "c3", 0 )  : ( "N/A", "DMA Enable (Stop)" ),
        ( "p15", "c11", 0, "c3", 1 )  : ( "N/A", "DMA Enable (Start)" ),
        ( "p15", "c11", 0, "c3", 2 )  : ( "N/A", "DMA Enable (Clear)" ),
        ( "p15", "c11", 0, "c4", 0 )  : ( "N/A", "DMA Control" ),
        ( "p15", "c11", 0, "c5", 0 )  : ( "N/A", "DMA Internal Start Address" ),
        ( "p15", "c11", 0, "c6", 0 )  : ( "N/A", "DMA External Start Address" ),
        ( "p15", "c11", 0, "c7", 0 )  : ( "N/A", "DMA Internal End Address" ),
        ( "p15", "c11", 0, "c8", 0 )  : ( "N/A", "DMA Channel Status" ),
        ( "p15", "c11", 0, "c15", 0)  : ( "N/A", "DMA Context ID" ),

        # Reset management registers.
        ( "p15", "c12", 0, "c0", 0 )  : ( "VBAR", "Vector Base Address Register" ),
        ( "p15", "c12", 0, "c0", 1 )  : ( "RVBAR", "Reset Vector Base Address Register" ,
                                          "MVBAR", "Monitor Vector Base Address Register" ),
        ( "p15", "c12", 0, "c0", 2 )  : ( "RMR", "Reset Management Register" ),
        ( "p15", "c12", 4, "c0", 2 )  : ( "HRMR", "Hyp Reset Management Register" ),

        ( "p15", "c12", 0, "c1", 0 )  : ( "ISR", "Interrupt Status Register" ),
        ( "p15", "c12", 4, "c0", 0 )  : ( "HVBAR", "Hyp Vector Base Address Register" ),

        ( "p15", "c13", 0, "c0", 0 )  : ( "FCSEIDR", "FCSE Process ID register" ),
        ( "p15", "c13", 0, "c0", 1 )  : ( "CONTEXTIDR", "Context ID Register" ),
        ( "p15", "c13", 0, "c0", 2 )  : ( "TPIDRURW", "PL0 Read/Write Software Thread ID Register" ),
        ( "p15", "c13", 0, "c0", 3 )  : ( "TPIDRURO", "PL0 Read-Only Software Thread ID Register" ),
        ( "p15", "c13", 0, "c0", 4 )  : ( "TPIDRPRW", "PL1 Software Thread ID Register" ),
        ( "p15", "c13", 4, "c0", 2 )  : ( "HTPIDR", "Hyp Software Thread ID Register" ),

        # Generic timer registers.
        ( "p15", "c14", 0, "c0", 0 )  : ( "CNTFRQ", "Counter-timer Frequency register" ),
        ( "p15", "c14", 0, "c1", 0 )  : ( "CNTKCTL", "Counter-timer Kernel Control register" ),
        ( "p15", "c14", 0, "c2", 0 )  : ( "CNTP_TVAL", "Counter-timer Physical Timer TimerValue register",
                                          "CNTHP_TVAL", "Counter-timer Hyp Physical Timer TimerValue register",
                                          "CNTHPS_TVAL", "Counter-timer Secure Physical Timer TimerValue Register (EL2)" ),
        ( "p15", "c14", 0, "c2", 1 )  : ( "CNTP_CTL", "Counter-timer Physical Timer Control register",
                                          "CNTHP_CTL", "Counter-timer Hyp Physical Timer Control register",
                                          "CNTHPS_CTL", "Counter-timer Secure Physical Timer Control Register (EL2)" ),
        ( "p15", "c14", 0, "c3", 0 )  : ( "CNTV_TVAL", "Counter-timer Virtual Timer TimerValue register",
                                          "CNTHV_TVAL", "Counter-timer Virtual Timer TimerValue register (EL2)",
                                          "CNTHVS_TVAL", "Counter-timer Secure Virtual Timer TimerValue Register (EL2)" ),
        ( "p15", "c14", 0, "c3", 1 )  : ( "CNTV_CTL", "Counter-timer Virtual Timer Control register",
                                          "CNTHV_CTL", "Counter-timer Virtual Timer Control register (EL2)",
                                          "CNTHVS_CTL", "Counter-timer Secure Virtual Timer Control Register (EL2)" ),
        ( "p15", "c14", 4, "c1", 0 )  : ( "CNTHCTL", "Counter-timer Hyp Control register" ),
        ( "p15", "c14", 4, "c2", 0 )  : ( "CNTHP_TVAL", "Counter-timer Hyp Physical Timer TimerValue register" ),
        ( "p15", "c14", 4, "c2", 1 )  : ( "CNTHP_CTL", "Counter-timer Hyp Physical Timer Control register" ),

        # Generic interrupt controller registers.
        ( "p15", "c4", 0, "c6", 0 )   : ( "ICC_PMR", "Interrupt Controller Interrupt Priority Mask Register",
                                          "ICV_PMR", "Interrupt Controller Virtual Interrupt Priority Mask Register" ),
        ( "p15", "c12", 0, "c8", 0 )  : ( "ICC_IAR0", "Interrupt Controller Interrupt Acknowledge Register 0",
                                          "ICV_IAR0", "Interrupt Controller Virtual Interrupt Acknowledge Register 0" ),
        ( "p15", "c12", 0, "c8", 1 )  : ( "ICC_EOIR0", "Interrupt Controller End Of Interrupt Register 0",
                                          "ICV_EOIR0", "Interrupt Controller Virtual End Of Interrupt Register 0" ),
        ( "p15", "c12", 0, "c8", 2 )  : ( "ICC_HPPIR0", "Interrupt Controller Highest Priority Pending Interrupt Register 0",
                                          "ICV_HPPIR0", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 0" ),
        ( "p15", "c12", 0, "c8", 3 )  : ( "ICC_BPR0", "Interrupt Controller Binary Point Register 0",
                                          "ICV_BPR0", "Interrupt Controller Virtual Binary Point Register 0" ),
        ( "p15", "c12", 0, "c8", 4 )  : ( "ICC_AP0R0", "Interrupt Controller Active Priorities Group 0 Register 0",
                                          "ICV_AP0R0", "Interrupt Controller Virtual Active Priorities Group 0 Register 0" ),
        ( "p15", "c12", 0, "c8", 5 )  : ( "ICC_AP0R1", "Interrupt Controller Active Priorities Group 0 Register 1",
                                          "ICV_AP0R1", "Interrupt Controller Virtual Active Priorities Group 0 Register 1" ),
        ( "p15", "c12", 0, "c8", 6 )  : ( "ICC_AP0R2", "Interrupt Controller Active Priorities Group 0 Register 2",
                                          "ICV_AP0R2", "Interrupt Controller Virtual Active Priorities Group 0 Register 2" ),
        ( "p15", "c12", 0, "c8", 7 )  : ( "ICC_AP0R3", "Interrupt Controller Active Priorities Group 0 Register 3",
                                          "ICV_AP0R3", "Interrupt Controller Virtual Active Priorities Group 0 Register 3" ),
        ( "p15", "c12", 0, "c9", 0 )  : ( "ICC_AP1R0", "Interrupt Controller Active Priorities Group 1 Register 0",
                                          "ICV_AP1R0", "Interrupt Controller Virtual Active Priorities Group 1 Register 0" ),
        ( "p15", "c12", 0, "c9", 1 )  : ( "ICC_AP1R1", "Interrupt Controller Active Priorities Group 1 Register 1",
                                          "ICV_AP1R1", "Interrupt Controller Virtual Active Priorities Group 1 Register 1" ),
        ( "p15", "c12", 0, "c9", 2 )  : ( "ICC_AP1R2", "Interrupt Controller Active Priorities Group 1 Register 2",
                                          "ICV_AP1R2", "Interrupt Controller Virtual Active Priorities Group 1 Register 2" ),
        ( "p15", "c12", 0, "c9", 3 )  : ( "ICC_AP1R3", "Interrupt Controller Active Priorities Group 1 Register 3",
                                          "ICV_AP1R3", "Interrupt Controller Virtual Active Priorities Group 1 Register 3" ),
        ( "p15", "c12", 0, "c11", 1 ) : ( "ICC_DIR", "Interrupt Controller Deactivate Interrupt Register",
                                          "ICV_DIR", "Interrupt Controller Deactivate Virtual Interrupt Register" ),
        ( "p15", "c12", 0, "c11", 3 ) : ( "ICC_RPR", "Interrupt Controller Running Priority Register",
                                          "ICV_RPR", "Interrupt Controller Virtual Running Priority Register" ),
        ( "p15", "c12", 0, "c12", 0 ) : ( "ICC_IAR1", "Interrupt Controller Interrupt Acknowledge Register 1",
                                          "ICV_IAR1", "Interrupt Controller Virtual Interrupt Acknowledge Register 1" ),
        ( "p15", "c12", 0, "c12", 1 ) : ( "ICC_EOIR1", "Interrupt Controller End Of Interrupt Register 1",
                                          "ICV_EOIR1", "Interrupt Controller Virtual End Of Interrupt Register 1" ),
        ( "p15", "c12", 0, "c12", 2 ) : ( "ICC_HPPIR1", "Interrupt Controller Highest Priority Pending Interrupt Register 1",
                                          "ICV_HPPIR1", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 1" ),
        ( "p15", "c12", 0, "c12", 3 ) : ( "ICC_BPR1", "Interrupt Controller Binary Point Register 1",
                                          "ICV_BPR1", "Interrupt Controller Virtual Binary Point Register 1" ),
        ( "p15", "c12", 0, "c12", 4 ) : ( "ICC_CTLR", "Interrupt Controller Control Register",
                                          "ICV_CTLR", "Interrupt Controller Virtual Control Register" ),
        ( "p15", "c12", 0, "c12", 5 ) : ( "ICC_SRE", "Interrupt Controller System Register Enable register" ),
        ( "p15", "c12", 0, "c12", 6 ) : ( "ICC_IGRPEN0", "Interrupt Controller Interrupt Group 0 Enable register",
                                          "ICV_IGRPEN0", "Interrupt Controller Virtual Interrupt Group 0 Enable register" ),
        ( "p15", "c12", 0, "c12", 7 ) : ( "ICC_IGRPEN1", "Interrupt Controller Interrupt Group 1 Enable register",
                                          "ICV_IGRPEN1", "Interrupt Controller Virtual Interrupt Group 1 Enable register" ),
        ( "p15", "c12", 4, "c8", 0 )  : ( "ICH_AP0R0", "Interrupt Controller Hyp Active Priorities Group 0 Register 0" ),
        ( "p15", "c12", 4, "c8", 1 )  : ( "ICH_AP0R1", "Interrupt Controller Hyp Active Priorities Group 0 Register 1" ),
        ( "p15", "c12", 4, "c8", 2 )  : ( "ICH_AP0R2", "Interrupt Controller Hyp Active Priorities Group 0 Register 2" ),
        ( "p15", "c12", 4, "c8", 3 )  : ( "ICH_AP0R3", "Interrupt Controller Hyp Active Priorities Group 0 Register 3" ),
        ( "p15", "c12", 4, "c9", 0 )  : ( "ICH_AP1R0", "Interrupt Controller Hyp Active Priorities Group 1 Register 0" ),
        ( "p15", "c12", 4, "c9", 1 )  : ( "ICH_AP1R1", "Interrupt Controller Hyp Active Priorities Group 1 Register 1" ),
        ( "p15", "c12", 4, "c9", 2 )  : ( "ICH_AP1R2", "Interrupt Controller Hyp Active Priorities Group 1 Register 2" ),
        ( "p15", "c12", 4, "c9", 3 )  : ( "ICH_AP1R3", "Interrupt Controller Hyp Active Priorities Group 1 Register 3" ),
        ( "p15", "c12", 4, "c9", 5 )  : ( "ICC_HSRE", "Interrupt Controller Hyp System Register Enable register" ),
        ( "p15", "c12", 4, "c11", 0 ) : ( "ICH_HCR", "Interrupt Controller Hyp Control Register" ),
        ( "p15", "c12", 4, "c11", 1 ) : ( "ICH_VTR", "Interrupt Controller VGIC Type Register" ),
        ( "p15", "c12", 4, "c11", 2 ) : ( "ICH_MISR", "Interrupt Controller Maintenance Interrupt State Register" ),
        ( "p15", "c12", 4, "c11", 3 ) : ( "ICH_EISR", "Interrupt Controller End of Interrupt Status Register" ),
        ( "p15", "c12", 4, "c11", 5 ) : ( "ICH_ELRSR", "Interrupt Controller Empty List Register Status Register" ),
        ( "p15", "c12", 4, "c11", 7 ) : ( "ICH_VMCR", "Interrupt Controller Virtual Machine Control Register" ),
        ( "p15", "c12", 4, "c12", 0 ) : ( "ICH_LR0", "Interrupt Controller List Register 0" ),
        ( "p15", "c12", 4, "c12", 1 ) : ( "ICH_LR1", "Interrupt Controller List Register 1" ),
        ( "p15", "c12", 4, "c12", 2 ) : ( "ICH_LR2", "Interrupt Controller List Register 2" ),
        ( "p15", "c12", 4, "c12", 3 ) : ( "ICH_LR3", "Interrupt Controller List Register 3" ),
        ( "p15", "c12", 4, "c12", 4 ) : ( "ICH_LR4", "Interrupt Controller List Register 4" ),
        ( "p15", "c12", 4, "c12", 5 ) : ( "ICH_LR5", "Interrupt Controller List Register 5" ),
        ( "p15", "c12", 4, "c12", 6 ) : ( "ICH_LR6", "Interrupt Controller List Register 6" ),
        ( "p15", "c12", 4, "c12", 7 ) : ( "ICH_LR7", "Interrupt Controller List Register 7" ),
        ( "p15", "c12", 4, "c13", 0 ) : ( "ICH_LR8", "Interrupt Controller List Register 8" ),
        ( "p15", "c12", 4, "c13", 1 ) : ( "ICH_LR9", "Interrupt Controller List Register 9" ),
        ( "p15", "c12", 4, "c13", 2 ) : ( "ICH_LR10", "Interrupt Controller List Register 10" ),
        ( "p15", "c12", 4, "c13", 3 ) : ( "ICH_LR11", "Interrupt Controller List Register 11" ),
        ( "p15", "c12", 4, "c13", 4 ) : ( "ICH_LR12", "Interrupt Controller List Register 12" ),
        ( "p15", "c12", 4, "c13", 5 ) : ( "ICH_LR13", "Interrupt Controller List Register 13" ),
        ( "p15", "c12", 4, "c13", 6 ) : ( "ICH_LR14", "Interrupt Controller List Register 14" ),
        ( "p15", "c12", 4, "c13", 7 ) : ( "ICH_LR15", "Interrupt Controller List Register 15" ),
        ( "p15", "c12", 4, "c14", 0 ) : ( "ICH_LRC0", "Interrupt Controller List Register 0" ),
        ( "p15", "c12", 4, "c14", 1 ) : ( "ICH_LRC1", "Interrupt Controller List Register 1" ),
        ( "p15", "c12", 4, "c14", 2 ) : ( "ICH_LRC2", "Interrupt Controller List Register 2" ),
        ( "p15", "c12", 4, "c14", 3 ) : ( "ICH_LRC3", "Interrupt Controller List Register 3" ),
        ( "p15", "c12", 4, "c14", 4 ) : ( "ICH_LRC4", "Interrupt Controller List Register 4" ),
        ( "p15", "c12", 4, "c14", 5 ) : ( "ICH_LRC5", "Interrupt Controller List Register 5" ),
        ( "p15", "c12", 4, "c14", 6 ) : ( "ICH_LRC6", "Interrupt Controller List Register 6" ),
        ( "p15", "c12", 4, "c14", 7 ) : ( "ICH_LRC7", "Interrupt Controller List Register 7" ),
        ( "p15", "c12", 4, "c15", 0 ) : ( "ICH_LRC8", "Interrupt Controller List Register 8" ),
        ( "p15", "c12", 4, "c15", 1 ) : ( "ICH_LRC9", "Interrupt Controller List Register 9" ),
        ( "p15", "c12", 4, "c15", 2 ) : ( "ICH_LRC10", "Interrupt Controller List Register 10" ),
        ( "p15", "c12", 4, "c15", 3 ) : ( "ICH_LRC11", "Interrupt Controller List Register 11" ),
        ( "p15", "c12", 4, "c15", 4 ) : ( "ICH_LRC12", "Interrupt Controller List Register 12" ),
        ( "p15", "c12", 4, "c15", 5 ) : ( "ICH_LRC13", "Interrupt Controller List Register 13" ),
        ( "p15", "c12", 4, "c15", 6 ) : ( "ICH_LRC14", "Interrupt Controller List Register 14" ),
        ( "p15", "c12", 4, "c15", 7 ) : ( "ICH_LRC15", "Interrupt Controller List Register 15" ),
        ( "p15", "c12", 6, "c12", 4 ) : ( "ICC_MCTLR", "Interrupt Controller Monitor Control Register" ),
        ( "p15", "c12", 6, "c12", 5 ) : ( "ICC_MSRE", "Interrupt Controller Monitor System Register Enable register" ),
        ( "p15", "c12", 6, "c12", 7 ) : ( "ICC_MGRPEN1", "Interrupt Controller Monitor Interrupt Group 1 Enable register" ),

        ( "p15", "c15", 0, "c0", 0 )  : ( "IL1Data0", "Instruction L1 Data n Register" ),
        ( "p15", "c15", 0, "c0", 1 )  : ( "IL1Data1", "Instruction L1 Data n Register" ),
        ( "p15", "c15", 0, "c0", 2 )  : ( "IL1Data2", "Instruction L1 Data n Register" ),
        ( "p15", "c15", 0, "c1", 0 )  : ( "DL1Data0", "Data L1 Data n Register" ),
        ( "p15", "c15", 0, "c1", 1 )  : ( "DL1Data1", "Data L1 Data n Register" ),
        ( "p15", "c15", 0, "c1", 2 )  : ( "DL1Data2", "Data L1 Data n Register" ),
        ( "p15", "c15", 0, "c2", 0 )  : ( "N/A", "Data Memory Remap" ), # ARM11
        ( "p15", "c15", 0, "c2", 1 )  : ( "N/A", "Instruction Memory Remap" ), # ARM11
        ( "p15", "c15", 0, "c2", 2 )  : ( "N/A", "DMA Memory Remap" ), # ARM11
        ( "p15", "c15", 0, "c2", 3 )  : ( "N/A", "Peripheral Port Memory Remap" ), # ARM11
        ( "p15", "c15", 0, "c4", 0 )  : ( "RAMINDEX", "RAM Index Register" ),
        ( "p15", "c15", 0, "c12", 0 ) : ( "N/A", "Performance Monitor Control" ), #ARM11
        ( "p15", "c15", 0, "c12", 1 ) : ( "CCNT", "Cycle Counter" ), #ARM11
        ( "p15", "c15", 0, "c12", 2 ) : ( "PMN0", "Count 0" ), #ARM11
        ( "p15", "c15", 0, "c12", 3 ) : ( "PMN1", "Count 1" ), #ARM11
        ( "p15", "c15", 1, "c0", 0 )  : ( "L2ACTLR", "L2 Auxiliary Control Register" ),
        ( "p15", "c15", 1, "c0", 3 )  : ( "L2FPR", "L2 Prefetch Control Register" ),
        ( "p15", "c15", 3, "c0", 0 )  : ( "N/A", "Data Debug Cache" ), # ARM11
        ( "p15", "c15", 3, "c0", 1 )  : ( "N/A", "Instruction Debug Cache" ), # ARM11
        ( "p15", "c15", 3, "c2", 0 )  : ( "N/A", "Data Tag RAM Read Operation" ), # ARM11
        ( "p15", "c15", 3, "c2", 1 )  : ( "N/A", "Instruction Tag RAM Read Operation" ), # ARM11
        ( "p15", "c15", 4, "c0", 0 )  : ( "CBAR", "Configuration Base Address Register" ),
        ( "p15", "c15", 5, "c4", 0 )  : ( "N/A", "Data MicroTLB Index" ), # ARM11
        ( "p15", "c15", 5, "c4", 1 )  : ( "N/A", "Instruction MicroTLB Index" ), # ARM11
        ( "p15", "c15", 5, "c4", 2 )  : ( "N/A", "Read Main TLB Entry" ), # ARM11
        ( "p15", "c15", 5, "c4", 4 )  : ( "N/A", "Write Main TLB Entry" ), # ARM11
        ( "p15", "c15", 5, "c5", 0 )  : ( "N/A", "Data MicroTLB VA" ), # ARM11
        ( "p15", "c15", 5, "c5", 1 )  : ( "N/A", "Instruction MicroTLB VA" ), # ARM11
        ( "p15", "c15", 5, "c5", 2 )  : ( "N/A", "Main TLB VA" ), # ARM11
        ( "p15", "c15", 5, "c7", 0 )  : ( "N/A", "Data MicroTLB Attribute" ), # ARM11
        ( "p15", "c15", 5, "c7", 1 )  : ( "N/A", "Instruction MicroTLB Attribute" ), # ARM11
        ( "p15", "c15", 5, "c7", 2 )  : ( "N/A", "Main TLB Attribute" ), # ARM11
        ( "p15", "c15", 7, "c0", 0 )  : ( "N/A", "Cache Debug Control" ), # ARM11
        ( "p15", "c15", 7, "c1", 0 )  : ( "N/A", "TLB Debug Control" ), # ARM11

        # Preload Engine control registers
        ( "p15", "c11", 0, "c0", 0 )   : ( "PLEIDR", "Preload Engine ID Register" ),
        ( "p15", "c11", 0, "c0", 2 )   : ( "PLEASR", "Preload Engine Activity Status Register" ),
        ( "p15", "c11", 0, "c0", 4 )   : ( "PLEFSR", "Preload Engine FIFO Status Register" ),
        ( "p15", "c11", 0, "c1", 0 )   : ( "PLEUAR", "Preload Engine User Accessibility Register" ),
        ( "p15", "c11", 0, "c1", 1 )   : ( "PLEPCR", "Preload Engine Parameters Control Register" ),

        # Preload Engine operations
        ( "p15", "c11", 0, "c2", 1 )   : ( "PLEFF", "Preload Engine FIFO flush operation" ),
        ( "p15", "c11", 0, "c3", 0 )   : ( "PLEPC", "Preload Engine pause channel operation" ),
        ( "p15", "c11", 0, "c3", 1 )   : ( "PLERC", "Preload Engine resume channel operation" ),
        ( "p15", "c11", 0, "c3", 2 )   : ( "PLEKC", "Preload Engine kill channel operation" ),

        # Jazelle registers
        ( "p14", "c0", 7, "c0", 0 )   : ( "JIDR", "Jazelle ID Register" ),
        ( "p14", "c1", 7, "c0", 0 )   : ( "JOSCR", "Jazelle OS Control Register" ),
        ( "p14", "c2", 7, "c0", 0 )   : ( "JMCR", "Jazelle Main Configuration Register" ),

        # Debug registers
        ( "p15", "c4", 3, "c5", 0 )   : ( "DSPSR", "Debug Saved Program Status Register" ),
        ( "p15", "c4", 3, "c5", 1 )   : ( "DLR", "Debug Link Register" ),
        ( "p15", "c0", 0, "c3", 5 )   : ( "ID_DFR1", "Debug Feature Register 1" ),
        ( "p14", "c0", 0, "c0", 0 )   : ( "DBGDIDR", "Debug ID Register" ),
        ( "p14", "c0", 0, "c6", 0 )   : ( "DBGWFAR", "Debug Watchpoint Fault Address Register" ),
        ( "p14", "c0", 0, "c6", 2 )   : ( "DBGOSECCR", "Debug OS Lock Exception Catch Control Register" ),
        ( "p14", "c0", 0, "c7", 0 )   : ( "DBGVCR", "Debug Vector Catch Register" ),
        ( "p14", "c0", 0, "c0", 2 )   : ( "DBGDTRRXext", "Debug OS Lock Data Transfer Register, Receive, External View" ),
        ( "p14", "c0", 0, "c2", 0 )   : ( "DBGDCCINT", "DCC Interrupt Enable Register" ),
        ( "p14", "c0", 0, "c2", 2 )   : ( "DBGDSCRext", "Debug Status and Control Register, External View" ),
        ( "p14", "c0", 0, "c3", 2 )   : ( "DBGDTRTXext", "Debug OS Lock Data Transfer Register, Transmit" ),
        ( "p14", "c0", 0, "c0", 4 )   : ( "DBGBVR0", "Debug Breakpoint Value Register 0" ),
        ( "p14", "c0", 0, "c1", 4 )   : ( "DBGBVR1", "Debug Breakpoint Value Register 1" ),
        ( "p14", "c0", 0, "c2", 4 )   : ( "DBGBVR2", "Debug Breakpoint Value Register 2" ),
        ( "p14", "c0", 0, "c3", 4 )   : ( "DBGBVR3", "Debug Breakpoint Value Register 3" ),
        ( "p14", "c0", 0, "c4", 4 )   : ( "DBGBVR4", "Debug Breakpoint Value Register 4" ),
        ( "p14", "c0", 0, "c5", 4 )   : ( "DBGBVR5", "Debug Breakpoint Value Register 5" ),
        ( "p14", "c0", 0, "c6", 4 )   : ( "DBGBVR6", "Debug Breakpoint Value Register 6" ),
        ( "p14", "c0", 0, "c7", 4 )   : ( "DBGBVR7", "Debug Breakpoint Value Register 7" ),
        ( "p14", "c0", 0, "c8", 4 )   : ( "DBGBVR8", "Debug Breakpoint Value Register 8" ),
        ( "p14", "c0", 0, "c9", 4 )   : ( "DBGBVR9", "Debug Breakpoint Value Register 9" ),
        ( "p14", "c0", 0, "c10", 4 )  : ( "DBGBVR10", "Debug Breakpoint Value Register 10" ),
        ( "p14", "c0", 0, "c11", 4 )  : ( "DBGBVR11", "Debug Breakpoint Value Register 11" ),
        ( "p14", "c0", 0, "c12", 4 )  : ( "DBGBVR12", "Debug Breakpoint Value Register 12" ),
        ( "p14", "c0", 0, "c13", 4 )  : ( "DBGBVR13", "Debug Breakpoint Value Register 13" ),
        ( "p14", "c0", 0, "c14", 4 )  : ( "DBGBVR14", "Debug Breakpoint Value Register 14" ),
        ( "p14", "c0", 0, "c15", 4 )  : ( "DBGBVR15", "Debug Breakpoint Value Register 15" ),
        ( "p14", "c0", 0, "c0", 5 )   : ( "DBGBCR0", "Debug Breakpoint Control Register 0" ),
        ( "p14", "c0", 0, "c1", 5 )   : ( "DBGBCR1", "Debug Breakpoint Control Register 1" ),
        ( "p14", "c0", 0, "c2", 5 )   : ( "DBGBCR2", "Debug Breakpoint Control Register 2" ),
        ( "p14", "c0", 0, "c3", 5 )   : ( "DBGBCR3", "Debug Breakpoint Control Register 3" ),
        ( "p14", "c0", 0, "c4", 5 )   : ( "DBGBCR4", "Debug Breakpoint Control Register 4" ),
        ( "p14", "c0", 0, "c5", 5 )   : ( "DBGBCR5", "Debug Breakpoint Control Register 5" ),
        ( "p14", "c0", 0, "c6", 5 )   : ( "DBGBCR6", "Debug Breakpoint Control Register 6" ),
        ( "p14", "c0", 0, "c7", 5 )   : ( "DBGBCR7", "Debug Breakpoint Control Register 7" ),
        ( "p14", "c0", 0, "c8", 5 )   : ( "DBGBCR8", "Debug Breakpoint Control Register 8" ),
        ( "p14", "c0", 0, "c9", 5 )   : ( "DBGBCR9", "Debug Breakpoint Control Register 9" ),
        ( "p14", "c0", 0, "c10", 5 )  : ( "DBGBCR10", "Debug Breakpoint Control Register 10" ),
        ( "p14", "c0", 0, "c11", 5 )  : ( "DBGBCR11", "Debug Breakpoint Control Register 11" ),
        ( "p14", "c0", 0, "c12", 5 )  : ( "DBGBCR12", "Debug Breakpoint Control Register 12" ),
        ( "p14", "c0", 0, "c13", 5 )  : ( "DBGBCR13", "Debug Breakpoint Control Register 13" ),
        ( "p14", "c0", 0, "c14", 5 )  : ( "DBGBCR14", "Debug Breakpoint Control Register 14" ),
        ( "p14", "c0", 0, "c15", 5 )  : ( "DBGBCR15", "Debug Breakpoint Control Register 15" ),
        ( "p14", "c0", 0, "c0", 6 )   : ( "DBGWVR0", "Debug Watchpoint Value Register 0" ),
        ( "p14", "c0", 0, "c1", 6 )   : ( "DBGWVR1", "Debug Watchpoint Value Register 1" ),
        ( "p14", "c0", 0, "c2", 6 )   : ( "DBGWVR2", "Debug Watchpoint Value Register 2" ),
        ( "p14", "c0", 0, "c3", 6 )   : ( "DBGWVR3", "Debug Watchpoint Value Register 3" ),
        ( "p14", "c0", 0, "c4", 6 )   : ( "DBGWVR4", "Debug Watchpoint Value Register 4" ),
        ( "p14", "c0", 0, "c5", 6 )   : ( "DBGWVR5", "Debug Watchpoint Value Register 5" ),
        ( "p14", "c0", 0, "c6", 6 )   : ( "DBGWVR6", "Debug Watchpoint Value Register 6" ),
        ( "p14", "c0", 0, "c7", 6 )   : ( "DBGWVR7", "Debug Watchpoint Value Register 7" ),
        ( "p14", "c0", 0, "c8", 6 )   : ( "DBGWVR8", "Debug Watchpoint Value Register 8" ),
        ( "p14", "c0", 0, "c9", 6 )   : ( "DBGWVR9", "Debug Watchpoint Value Register 9" ),
        ( "p14", "c0", 0, "c10", 6 )  : ( "DBGWVR10", "Debug Watchpoint Value Register 10" ),
        ( "p14", "c0", 0, "c11", 6 )  : ( "DBGWVR11", "Debug Watchpoint Value Register 11" ),
        ( "p14", "c0", 0, "c12", 6 )  : ( "DBGWVR12", "Debug Watchpoint Value Register 12" ),
        ( "p14", "c0", 0, "c13", 6 )  : ( "DBGWVR13", "Debug Watchpoint Value Register 13" ),
        ( "p14", "c0", 0, "c14", 6 )  : ( "DBGWVR14", "Debug Watchpoint Value Register 14" ),
        ( "p14", "c0", 0, "c15", 6 )  : ( "DBGWVR15", "Debug Watchpoint Value Register 15" ),
        ( "p14", "c0", 0, "c0", 7 )   : ( "DBGWCR0", "Debug Watchpoint Control Register 0" ),
        ( "p14", "c0", 0, "c1", 7 )   : ( "DBGWCR1", "Debug Watchpoint Control Register 1" ),
        ( "p14", "c0", 0, "c2", 7 )   : ( "DBGWCR2", "Debug Watchpoint Control Register 2" ),
        ( "p14", "c0", 0, "c3", 7 )   : ( "DBGWCR3", "Debug Watchpoint Control Register 3" ),
        ( "p14", "c0", 0, "c4", 7 )   : ( "DBGWCR4", "Debug Watchpoint Control Register 4" ),
        ( "p14", "c0", 0, "c5", 7 )   : ( "DBGWCR5", "Debug Watchpoint Control Register 5" ),
        ( "p14", "c0", 0, "c6", 7 )   : ( "DBGWCR6", "Debug Watchpoint Control Register 6" ),
        ( "p14", "c0", 0, "c7", 7 )   : ( "DBGWCR7", "Debug Watchpoint Control Register 7" ),
        ( "p14", "c0", 0, "c8", 7 )   : ( "DBGWCR8", "Debug Watchpoint Control Register 8" ),
        ( "p14", "c0", 0, "c9", 7 )   : ( "DBGWCR9", "Debug Watchpoint Control Register 9" ),
        ( "p14", "c0", 0, "c10", 7 )  : ( "DBGWCR10", "Debug Watchpoint Control Register 10" ),
        ( "p14", "c0", 0, "c11", 7 )  : ( "DBGWCR11", "Debug Watchpoint Control Register 11" ),
        ( "p14", "c0", 0, "c12", 7 )  : ( "DBGWCR12", "Debug Watchpoint Control Register 12" ),
        ( "p14", "c0", 0, "c13", 7 )  : ( "DBGWCR13", "Debug Watchpoint Control Register 13" ),
        ( "p14", "c0", 0, "c14", 7 )  : ( "DBGWCR14", "Debug Watchpoint Control Register 14" ),
        ( "p14", "c0", 0, "c15", 7 )  : ( "DBGWCR15", "Debug Watchpoint Control Register 15" ),
        ( "p14", "c1", 0, "c0", 1 )   : ( "DBGBXVR0", "Debug Breakpoint Extended Value Register 0" ),
        ( "p14", "c1", 0, "c1", 1 )   : ( "DBGBXVR1", "Debug Breakpoint Extended Value Register 1" ),
        ( "p14", "c1", 0, "c2", 1 )   : ( "DBGBXVR2", "Debug Breakpoint Extended Value Register 2" ),
        ( "p14", "c1", 0, "c3", 1 )   : ( "DBGBXVR3", "Debug Breakpoint Extended Value Register 3" ),
        ( "p14", "c1", 0, "c4", 1 )   : ( "DBGBXVR4", "Debug Breakpoint Extended Value Register 4" ),
        ( "p14", "c1", 0, "c5", 1 )   : ( "DBGBXVR5", "Debug Breakpoint Extended Value Register 5" ),
        ( "p14", "c1", 0, "c6", 1 )   : ( "DBGBXVR6", "Debug Breakpoint Extended Value Register 6" ),
        ( "p14", "c1", 0, "c7", 1 )   : ( "DBGBXVR7", "Debug Breakpoint Extended Value Register 7" ),
        ( "p14", "c1", 0, "c8", 1 )   : ( "DBGBXVR8", "Debug Breakpoint Extended Value Register 8" ),
        ( "p14", "c1", 0, "c9", 1 )   : ( "DBGBXVR9", "Debug Breakpoint Extended Value Register 9" ),
        ( "p14", "c1", 0, "c10", 1 )  : ( "DBGBXVR10", "Debug Breakpoint Extended Value Register 10" ),
        ( "p14", "c1", 0, "c11", 1 )  : ( "DBGBXVR11", "Debug Breakpoint Extended Value Register 11" ),
        ( "p14", "c1", 0, "c12", 1 )  : ( "DBGBXVR12", "Debug Breakpoint Extended Value Register 12" ),
        ( "p14", "c1", 0, "c13", 1 )  : ( "DBGBXVR13", "Debug Breakpoint Extended Value Register 13" ),
        ( "p14", "c1", 0, "c14", 1 )  : ( "DBGBXVR14", "Debug Breakpoint Extended Value Register 14" ),
        ( "p14", "c1", 0, "c15", 1 )  : ( "DBGBXVR15", "Debug Breakpoint Extended Value Register 15" ),
        ( "p14", "c1", 0, "c0", 4 )   : ( "DBGOSLAR", "Debug OS Lock Access Register" ),
        ( "p14", "c1", 0, "c1", 4 )   : ( "DBGOSLSR", "Debug OS Lock Status Register" ),
        ( "p14", "c1", 0, "c4", 4 )   : ( "DBGPRCR", "Debug Power Control Register" ),
        ( "p14", "c7", 0, "c14", 6 )  : ( "DBGAUTHSTATUS", "Debug Authentication Status register" ),
        ( "p14", "c7", 0, "c0", 7 )   : ( "DBGDEVID2", "Debug Device ID register 2" ),
        ( "p14", "c7", 0, "c1", 7 )   : ( "DBGDEVID1", "Debug Device ID register 1" ),
        ( "p14", "c7", 0, "c2", 7 )   : ( "DBGDEVID", "Debug Device ID register 0" ),
        ( "p14", "c7", 0, "c8", 6 )   : ( "DBGCLAIMSET", "Debug Claim Tag Set register" ),
        ( "p14", "c7", 0, "c9", 6 )   : ( "DBGCLAIMCLR", "Debug Claim Tag Clear register" ),
        ( "p14", "c0", 0, "c1", 0 )   : ( "DBGDSCRint", "Debug Status and Control Register, Internal View" ),
        ( "p14", "c0", 0, "c5", 0 )   : ( "DBGDTRRXint", "Debug Data Transfer Register, Receive",
                                          "DBGDTRTXint", "Debug Data Transfer Register, Transmit" ),
        ( "p14", "c1", 0, "c0", 0 )   : ( "DBGDRAR", "Debug ROM Address Register" ),
        ( "p14", "c1", 0, "c3", 4 )   : ( "DBGOSDLR", "Debug OS Double Lock Register" ),
        ( "p14", "c2", 0, "c0", 0 )   : ( "DBGDSAR", "Debug Self Address Register" ),
        ( "p15", "c1", 4, "c2", 1 )   : ( "HTRFCR", "Hyp Trace Filter Control Register" ),
        ( "p15", "c1", 0, "c2", 1 )   : ( "TRFCR", "Trace Filter Control Register" ),
}

# Aarch64 system registers.
# Extracted from the XML specifications for v8.7-A (2021-06).
AARCH64_SYSTEM_REGISTERS = {
        # Special purpose registers.
        ( 0b011, 0b000, "c4", "c2", 0b010 )   : ( "CurrentEL", "Current Exception Level" ),
        ( 0b011, 0b011, "c4", "c2", 0b001 )   : ( "DAIF", "Interrupt Mask Bits" ),
        ( 0b011, 0b000, "c4", "c0", 0b001 )   : ( "ELR_EL1", "Exception Link Register (EL1)" ),
        ( 0b011, 0b100, "c4", "c0", 0b001 )   : ( "ELR_EL2", "Exception Link Register (EL2)" ),
        ( 0b011, 0b101, "c4", "c0", 0b001 )   : ( "ELR_EL12", "Exception Link Register (EL1)" ),
        ( 0b011, 0b110, "c4", "c0", 0b001 )   : ( "ELR_EL3", "Exception Link Register (EL3)" ),
        ( 0b011, 0b011, "c4", "c4", 0b001 )   : ( "FPSR", "Floating-point Status Register" ),
        ( 0b011, 0b011, "c4", "c4", 0b000 )   : ( "FPCR", "Floating-point Control Register" ),
        ( 0b011, 0b011, "c4", "c2", 0b000 )   : ( "NZCV", "Condition Flags" ),
        ( 0b011, 0b000, "c4", "c1", 0b000 )   : ( "SP_EL0", "Stack Pointer (EL0)" ),
        ( 0b011, 0b100, "c4", "c1", 0b000 )   : ( "SP_EL1", "Stack Pointer (EL1)" ),
        ( 0b011, 0b110, "c4", "c1", 0b000 )   : ( "SP_EL2", "Stack Pointer (EL2)" ),
        ( 0b011, 0b000, "c4", "c2", 0b000 )   : ( "SPSel", "Stack Pointer Select" ),
        ( 0b011, 0b100, "c4", "c3", 0b001 )   : ( "SPSR_abt", "Saved Program Status Register (Abort mode)" ),
        ( 0b011, 0b000, "c4", "c0", 0b000 )   : ( "SPSR_EL1", "Saved Program Status Register (EL1)" ),
        ( 0b011, 0b100, "c4", "c0", 0b000 )   : ( "SPSR_EL2", "Saved Program Status Register (EL2)" ),
        ( 0b011, 0b101, "c4", "c0", 0b000 )   : ( "SPSR_EL12", "Saved Program Status Register (EL1)" ),
        ( 0b011, 0b110, "c4", "c0", 0b000 )   : ( "SPSR_EL3", "Saved Program Status Register (EL3)" ),
        ( 0b011, 0b100, "c4", "c3", 0b011 )   : ( "SPSR_fiq", "Saved Program Status Register (FIQ mode)" ),
        ( 0b011, 0b100, "c4", "c3", 0b000 )   : ( "SPSR_irq", "Saved Program Status Register (IRQ mode)" ),
        ( 0b011, 0b100, "c4", "c3", 0b010 )   : ( "SPSR_und", "Saved Program Status Register (Undefined mode)" ),
        ( 0b011, 0b011, "c4", "c2", 0b101 )   : ( "DIT", "Data Independent Timing" ),
        ( 0b011, 0b011, "c4", "c2", 0b110 )   : ( "SSBS", "Speculative Store Bypass Safe" ),
        ( 0b011, 0b011, "c4", "c2", 0b111 )   : ( "TCO", "Tag Check Override" ),

        # General system control registers.
        ( 0b011, 0b000, "c1", "c0", 0b001 )   : ( "ACTLR_EL1", "Auxiliary Control Register (EL1)" ),
        ( 0b011, 0b100, "c1", "c0", 0b001 )   : ( "ACTLR_EL2", "Auxiliary Control Register (EL2)" ),
        ( 0b011, 0b110, "c1", "c0", 0b001 )   : ( "ACTLR_EL3", "Auxiliary Control Register (EL3)" ),
        ( 0b011, 0b000, "c4", "c2", 0b011 )   : ( "PAN", "Privileged Access Never" ),
        ( 0b011, 0b000, "c4", "c2", 0b100 )   : ( "UAO", "User Access Override" ),
        ( 0b011, 0b000, "c5", "c1", 0b000 )   : ( "AFSR0_EL1", "Auxiliary Fault Status Register 0 (EL1)" ),
        ( 0b011, 0b100, "c5", "c1", 0b000 )   : ( "AFSR0_EL2", "Auxiliary Fault Status Register 0 (EL2)" ),
        ( 0b011, 0b101, "c5", "c1", 0b000 )   : ( "AFSR0_EL12", "Auxiliary Fault Status Register 0 (EL1)" ),
        ( 0b011, 0b110, "c5", "c1", 0b000 )   : ( "AFSR0_EL3", "Auxiliary Fault Status Register 0 (EL3)" ),
        ( 0b011, 0b000, "c5", "c1", 0b001 )   : ( "AFSR1_EL1", "Auxiliary Fault Status Register 1 (EL1)" ),
        ( 0b011, 0b100, "c5", "c1", 0b001 )   : ( "AFSR1_EL2", "Auxiliary Fault Status Register 1 (EL2)" ),
        ( 0b011, 0b101, "c5", "c1", 0b001 )   : ( "AFSR1_EL12", "Auxiliary Fault Status Register 1 (EL1)" ),
        ( 0b011, 0b110, "c5", "c1", 0b001 )   : ( "AFSR1_EL3", "Auxiliary Fault Status Register 1 (EL3)" ),
        ( 0b011, 0b001, "c0", "c0", 0b111 )   : ( "AIDR_EL1", "Auxiliary ID Register" ),
        ( 0b011, 0b000, "c10", "c3", 0b000 )  : ( "AMAIR_EL1", "Auxiliary Memory Attribute Indirection Register (EL1)" ),
        ( 0b011, 0b100, "c10", "c3", 0b000 )  : ( "AMAIR_EL2", "Auxiliary Memory Attribute Indirection Register (EL2)" ),
        ( 0b011, 0b101, "c10", "c3", 0b000 )  : ( "AMAIR_EL12", "Auxiliary Memory Attribute Indirection Register (EL1)" ),
        ( 0b011, 0b110, "c10", "c3", 0b000 )  : ( "AMAIR_EL3", "Auxiliary Memory Attribute Indirection Register (EL3)" ),
        ( 0b011, 0b001, "c0", "c0", 0b000 )   : ( "CCSIDR_EL1", "Current Cache Size ID Register" ),
        ( 0b011, 0b001, "c0", "c0", 0b010 )   : ( "CCSIDR2_EL1", "Current Cache Size ID Register 2" ),
        ( 0b011, 0b001, "c0", "c0", 0b001 )   : ( "CLIDR_EL1", "Cache Level ID Register" ),
        ( 0b011, 0b000, "c13", "c0", 0b001 )  : ( "CONTEXTIDR_EL1", "Context ID Register (EL1)" ),
        ( 0b011, 0b100, "c13", "c0", 0b001 )  : ( "CONTEXTIDR_EL2", "Context ID Register (EL2)" ),
        ( 0b011, 0b101, "c13", "c0", 0b001 )  : ( "CONTEXTIDR_EL12", "Context ID Register (EL1)" ),
        ( 0b011, 0b000, "c1", "c0", 0b010 )   : ( "CPACR_EL1", "Architectural Feature Access Control Register (EL1)" ),
        ( 0b011, 0b101, "c1", "c0", 0b010 )   : ( "CPACR_EL12", "Architectural Feature Access Control Register (EL1)" ),
        ( 0b011, 0b100, "c1", "c1", 0b010 )   : ( "CPTR_EL2", "Architectural Feature Trap Register (EL2)" ),
        ( 0b011, 0b110, "c1", "c1", 0b010 )   : ( "CPTR_EL3", "Architectural Feature Trap Register (EL3)" ),
        ( 0b011, 0b010, "c0", "c0", 0b000 )   : ( "CSSELR_EL1", "Cache Size Selection Register" ),
        ( 0b011, 0b011, "c0", "c0", 0b001 )   : ( "CTR_EL0", "Cache Type Register" ),
        ( 0b011, 0b100, "c3", "c0", 0b000 )   : ( "DACR32_EL2", "Domain Access Control Register" ),
        ( 0b011, 0b011, "c0", "c0", 0b111 )   : ( "DCZID_EL0", "Data Cache Zero ID register" ),
        ( 0b011, 0b000, "c5", "c2", 0b000 )   : ( "ESR_EL1", "Exception Syndrome Register (EL1)" ),
        ( 0b011, 0b100, "c5", "c2", 0b000 )   : ( "ESR_EL2", "Exception Syndrome Register (EL2)" ),
        ( 0b011, 0b101, "c5", "c2", 0b000 )   : ( "ESR_EL12", "Exception Syndrome Register (EL1)" ),
        ( 0b011, 0b110, "c5", "c2", 0b000 )   : ( "ESR_EL3", "Exception Syndrome Register (EL3)" ),
        ( 0b011, 0b000, "c6", "c0", 0b000 )   : ( "FAR_EL1", "Fault Address Register (EL1)" ),
        ( 0b011, 0b100, "c6", "c0", 0b000 )   : ( "FAR_EL2", "Fault Address Register (EL2)" ),
        ( 0b011, 0b101, "c6", "c0", 0b000 )   : ( "FAR_EL12", "Fault Address Register (EL1)" ),
        ( 0b011, 0b110, "c6", "c0", 0b000 )   : ( "FAR_EL3", "Fault Address Register (EL3)" ),
        ( 0b011, 0b100, "c5", "c3", 0b000 )   : ( "FPEXC32_EL2", "Floating-Point Exception Control register" ),
        ( 0b011, 0b100, "c1", "c1", 0b111 )   : ( "HACR_EL2", "Hypervisor Auxiliary Control Register" ),
        ( 0b011, 0b100, "c1", "c1", 0b000 )   : ( "HCR_EL2", "Hypervisor Configuration Register" ),
        ( 0b011, 0b100, "c6", "c0", 0b100 )   : ( "HPFAR_EL2", "Hypervisor IPA Fault Address Register" ),
        ( 0b011, 0b100, "c1", "c1", 0b011 )   : ( "HSTR_EL2", "Hypervisor System Trap Register" ),
        ( 0b011, 0b100, "c3", "c1", 0b110 )   : ( "HAFGRTR_EL2", "Hypervisor Activity Monitors Fine-Grained Read Trap Register" ),
        ( 0b011, 0b100, "c1", "c2", 0b010 )   : ( "HCRX_EL2", "Extended Hypervisor Configuration Register" ),
        ( 0b011, 0b100, "c3", "c1", 0b100 )   : ( "HDFGRTR_EL2", "Hypervisor Debug Fine-Grained Read Trap Register" ),
        ( 0b011, 0b100, "c3", "c1", 0b101 )   : ( "HDFGWTR_EL2", "Hypervisor Debug Fine-Grained Write Trap Register" ),
        ( 0b011, 0b100, "c1", "c1", 0b110 )   : ( "HFGITR_EL2", "Hypervisor Fine-Grained Instruction Trap Register" ),
        ( 0b011, 0b100, "c1", "c1", 0b100 )   : ( "HFGRTR_EL2", "Hypervisor Fine-Grained Read Trap Register" ),
        ( 0b011, 0b100, "c1", "c1", 0b101 )   : ( "HFGWTR_EL2", "Hypervisor Fine-Grained Write Trap Register" ),
        ( 0b011, 0b000, "c0", "c5", 0b100 )   : ( "ID_AA64AFR0_EL1", "AArch64 Auxiliary Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c5", 0b101 )   : ( "ID_AA64AFR1_EL1", "AArch64 Auxiliary Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c5", 0b000 )   : ( "ID_AA64DFR0_EL1", "AArch64 Debug Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c5", 0b001 )   : ( "ID_AA64DFR1_EL1", "AArch64 Debug Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c6", 0b000 )   : ( "ID_AA64ISAR0_EL1", "AArch64 Instruction Set Attribute Register 0" ),
        ( 0b011, 0b000, "c0", "c6", 0b001 )   : ( "ID_AA64ISAR1_EL1", "AArch64 Instruction Set Attribute Register 1" ),
        ( 0b011, 0b000, "c0", "c7", 0b000 )   : ( "ID_AA64MMFR0_EL1", "AArch64 Memory Model Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c7", 0b001 )   : ( "ID_AA64MMFR1_EL1", "AArch64 Memory Model Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c7", 0b010 )   : ( "ID_AA64MMFR2_EL1", "AArch64 Memory Model Feature Register 2" ),
        ( 0b011, 0b000, "c0", "c4", 0b000 )   : ( "ID_AA64PFR0_EL1", "AArch64 Processor Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c4", 0b001 )   : ( "ID_AA64PFR1_EL1", "AArch64 Processor Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c1", 0b011 )   : ( "ID_AFR0_EL1", "AArch32 Auxiliary Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c1", 0b010 )   : ( "ID_DFR0_EL1", "AArch32 Debug Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c2", 0b000 )   : ( "ID_ISAR0_EL1", "AArch32 Instruction Set Attribute Register 0" ),
        ( 0b011, 0b000, "c0", "c2", 0b001 )   : ( "ID_ISAR1_EL1", "AArch32 Instruction Set Attribute Register 1" ),
        ( 0b011, 0b000, "c0", "c2", 0b010 )   : ( "ID_ISAR2_EL1", "AArch32 Instruction Set Attribute Register 2" ),
        ( 0b011, 0b000, "c0", "c2", 0b011 )   : ( "ID_ISAR3_EL1", "AArch32 Instruction Set Attribute Register 3" ),
        ( 0b011, 0b000, "c0", "c2", 0b100 )   : ( "ID_ISAR4_EL1", "AArch32 Instruction Set Attribute Register 4" ),
        ( 0b011, 0b000, "c0", "c2", 0b101 )   : ( "ID_ISAR5_EL1", "AArch32 Instruction Set Attribute Register 5" ),
        ( 0b011, 0b000, "c0", "c2", 0b111 )   : ( "ID_ISAR6_EL1", "AArch32 Instruction Set Attribute Register 6" ),
        ( 0b011, 0b000, "c0", "c1", 0b100 )   : ( "ID_MMFR0_EL1", "AArch32 Memory Model Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c1", 0b101 )   : ( "ID_MMFR1_EL1", "AArch32 Memory Model Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c1", 0b110 )   : ( "ID_MMFR2_EL1", "AArch32 Memory Model Feature Register 2" ),
        ( 0b011, 0b000, "c0", "c1", 0b111 )   : ( "ID_MMFR3_EL1", "AArch32 Memory Model Feature Register 3" ),
        ( 0b011, 0b000, "c0", "c2", 0b110 )   : ( "ID_MMFR4_EL1", "AArch32 Memory Model Feature Register 4" ),
        ( 0b011, 0b000, "c0", "c1", 0b000 )   : ( "ID_PFR0_EL1", "AArch32 Processor Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c1", 0b001 )   : ( "ID_PFR1_EL1", "AArch32 Processor Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c6", 0b010 )   : ( "ID_AA64ISAR2_EL1", "AArch64 Instruction Set Attribute Register 2" ),
        ( 0b011, 0b000, "c0", "c4", 0b100 )   : ( "ID_AA64ZFR0_EL1", "SVE Feature ID register 0" ),
        ( 0b011, 0b000, "c0", "c3", 0b101 )   : ( "ID_DFR1_EL1", "Debug Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c3", 0b110 )   : ( "ID_MMFR5_EL1", "AArch32 Memory Model Feature Register 5" ),
        ( 0b011, 0b000, "c0", "c3", 0b100 )   : ( "ID_PFR2_EL1", "AArch32 Processor Feature Register 2" ),
        ( 0b011, 0b100, "c5", "c0", 0b001 )   : ( "IFSR32_EL2", "Instruction Fault Status Register (EL2)" ),
        ( 0b011, 0b000, "c12", "c1", 0b000 )  : ( "ISR_EL1", "Interrupt Status Register" ),
        ( 0b011, 0b000, "c10", "c2", 0b000 )  : ( "MAIR_EL1", "Memory Attribute Indirection Register (EL1)" ),
        ( 0b011, 0b100, "c10", "c2", 0b000 )  : ( "MAIR_EL2", "Memory Attribute Indirection Register (EL2)" ),
        ( 0b011, 0b101, "c10", "c2", 0b000 )  : ( "MAIR_EL12", "Memory Attribute Indirection Register (EL1)" ),
        ( 0b011, 0b110, "c10", "c2", 0b000 )  : ( "MAIR_EL3", "Memory Attribute Indirection Register (EL3)" ),
        ( 0b011, 0b000, "c0", "c0", 0b000 )   : ( "MIDR_EL1", "Main ID Register" ),
        ( 0b011, 0b000, "c0", "c0", 0b101 )   : ( "MPIDR_EL1", "Multiprocessor Affinity Register" ),
        ( 0b011, 0b000, "c0", "c3", 0b000 )   : ( "MVFR0_EL1", "AArch32 Media and VFP Feature Register 0" ),
        ( 0b011, 0b000, "c0", "c3", 0b001 )   : ( "MVFR1_EL1", "AArch32 Media and VFP Feature Register 1" ),
        ( 0b011, 0b000, "c0", "c3", 0b010 )   : ( "MVFR2_EL1", "AArch32 Media and VFP Feature Register 2" ),
        ( 0b011, 0b000, "c7", "c4", 0b000 )   : ( "PAR_EL1", "Physical Address Register" ),
        ( 0b011, 0b000, "c0", "c0", 0b110 )   : ( "REVIDR_EL1", "Revision ID Register" ),
        ( 0b011, 0b000, "c12", "c0", 0b010 )  : ( "RMR_EL1", "Reset Management Register (EL1)" ),
        ( 0b011, 0b100, "c12", "c0", 0b010 )  : ( "RMR_EL2", "Reset Management Register (EL2)" ),
        ( 0b011, 0b110, "c12", "c0", 0b010 )  : ( "RMR_EL3", "Reset Management Register (EL3)" ),
        ( 0b011, 0b000, "c12", "c0", 0b001 )  : ( "RVBAR_EL1", "Reset Vector Base Address Register (if EL2 and EL3 not implemented)" ),
        ( 0b011, 0b100, "c12", "c0", 0b001 )  : ( "RVBAR_EL2", "Reset Vector Base Address Register (if EL3 not implemented)" ),
        ( 0b011, 0b110, "c12", "c0", 0b001 )  : ( "RVBAR_EL3", "Reset Vector Base Address Register (if EL3 implemented)" ),
        ( 0b011, 0b110, "c1", "c1", 0b000 )   : ( "SCR_EL3", "Secure Configuration Register" ),
        ( 0b011, 0b110, "c1", "c1", 0b001 )   : ( "SDER_EL3", "AArch32 Secure Debug Enable Register" ),
        ( 0b011, 0b000, "c1", "c0", 0b000 )   : ( "SCTLR_EL1", "System Control Register (EL1)" ),
        ( 0b011, 0b100, "c1", "c0", 0b000 )   : ( "SCTLR_EL2", "System Control Register (EL2)" ),
        ( 0b011, 0b101, "c1", "c0", 0b000 )   : ( "SCTLR_EL12", "System Control Register (EL1)" ),
        ( 0b011, 0b110, "c1", "c0", 0b000 )   : ( "SCTLR_EL3", "System Control Register (EL3)" ),
        ( 0b011, 0b000, "c2", "c0", 0b010 )   : ( "TCR_EL1", "Translation Control Register (EL1)" ),
        ( 0b011, 0b100, "c2", "c0", 0b010 )   : ( "TCR_EL2", "Translation Control Register (EL2)" ),
        ( 0b011, 0b101, "c2", "c0", 0b010 )   : ( "TCR_EL12", "Translation Control Register (EL1)" ),
        ( 0b011, 0b110, "c2", "c0", 0b010 )   : ( "TCR_EL3", "Translation Control Register (EL3)" ),
        ( 0b011, 0b010, "c0", "c0", 0b000 )   : ( "TEECR32_EL1", "T32EE Configuration Register" ), # Not defined in 8.2 specifications.
        ( 0b011, 0b010, "c1", "c0", 0b000 )   : ( "TEEHBR32_EL1", "T32EE Handler Base Register" ), # Not defined in 8.2 specifications.
        ( 0b011, 0b011, "c13", "c0", 0b010 )  : ( "TPIDR_EL0", "EL0 Read/Write Software Thread ID Register" ),
        ( 0b011, 0b000, "c13", "c0", 0b100 )  : ( "TPIDR_EL1", "EL1 Software Thread ID Register" ),
        ( 0b011, 0b100, "c13", "c0", 0b010 )  : ( "TPIDR_EL2", "EL2 Software Thread ID Register" ),
        ( 0b011, 0b110, "c13", "c0", 0b010 )  : ( "TPIDR_EL3", "EL3 Software Thread ID Register" ),
        ( 0b011, 0b011, "c13", "c0", 0b011 )  : ( "TPIDRRO_EL0", "EL0 Read-Only Software Thread ID Register" ),
        ( 0b011, 0b000, "c2", "c0", 0b000 )   : ( "TTBR0_EL1", "Translation Table Base Register 0 (EL1)" ),
        ( 0b011, 0b100, "c2", "c0", 0b000 )   : ( "TTBR0_EL2", "Translation Table Base Register 0 (EL2)" ),
        ( 0b011, 0b101, "c2", "c0", 0b000 )   : ( "TTBR0_EL12", "Translation Table Base Register 0 (EL1)" ),
        ( 0b011, 0b110, "c2", "c0", 0b000 )   : ( "TTBR0_EL3", "Translation Table Base Register 0 (EL3)" ),
        ( 0b011, 0b000, "c2", "c0", 0b001 )   : ( "TTBR1_EL1", "Translation Table Base Register 1 (EL1)" ),
        ( 0b011, 0b100, "c2", "c0", 0b001 )   : ( "TTBR1_EL2", "Translation Table Base Register 1 (EL2)" ),
        ( 0b011, 0b101, "c2", "c0", 0b001 )   : ( "TTBR1_EL12", "Translation Table Base Register 1 (EL1)" ),
        ( 0b011, 0b000, "c12", "c0", 0b000 )  : ( "VBAR_EL1", "Vector Base Address Register (EL1)" ),
        ( 0b011, 0b100, "c12", "c0", 0b000 )  : ( "VBAR_EL2", "Vector Base Address Register (EL2)" ),
        ( 0b011, 0b101, "c12", "c0", 0b000 )  : ( "VBAR_EL12", "Vector Base Address Register (EL1)" ),
        ( 0b011, 0b110, "c12", "c0", 0b000 )  : ( "VBAR_EL3", "Vector Base Address Register (EL3)" ),
        ( 0b011, 0b100, "c0", "c0", 0b101 )   : ( "VMPIDR_EL2", "Virtualization Multiprocessor ID Register" ),
        ( 0b011, 0b100, "c0", "c0", 0b000 )   : ( "VPIDR_EL2", "Virtualization Processor ID Register" ),
        ( 0b011, 0b100, "c2", "c1", 0b010 )   : ( "VTCR_EL2", "Virtualization Translation Control Register" ),
        ( 0b011, 0b100, "c2", "c1", 0b000 )   : ( "VTTBR_EL2", "Virtualization Translation Table Base Register" ),
        ( 0b011, 0b001, "c15", "c2", 0b000 )  : ( "CPUACTLR_EL1", "CPU Auxiliary Control Register (EL1)" ),
        ( 0b011, 0b001, "c15", "c2", 0b001 )  : ( "CPUECTLR_EL1", "CPU Extended Control Register (EL1)" ),
        ( 0b011, 0b001, "c15", "c2", 0b010 )  : ( "CPUMERRSR_EL1", "CPU Memory Error Syndrome Register" ),
        ( 0b011, 0b001, "c15", "c2", 0b011 )  : ( "L2MERRSR_EL1", "L2 Memory Error Syndrome Register" ),
        ( 0b011, 0b000, "c13", "c0", 0b101 )  : ( "ACCDATA_EL1", "Accelerator Data" ),
        ( 0b011, 0b000, "c1", "c0", 0b110 )   : ( "GCR_EL1", "Tag Control Register." ),
        ( 0b011, 0b001, "c0", "c0", 0b100 )   : ( "GMID_EL1", " Multiple tag transfer ID register" ),
        ( 0b011, 0b000, "c1", "c0", 0b101 )   : ( "RGSR_EL1", "Random Allocation Tag Seed Register." ),
        ( 0b011, 0b011, "c2", "c4", 0b000 )   : ( "RNDR", "Random Number" ),
        ( 0b011, 0b011, "c2", "c4", 0b001 )   : ( "RNDRRS", "Reseeded Random Number" ),
        ( 0b011, 0b011, "c13", "c0", 0b111 )  : ( "SCXTNUM_EL0", "EL0 Read/Write Software Context Number" ),
        ( 0b011, 0b000, "c13", "c0", 0b111 )  : ( "SCXTNUM_EL1", "EL1 Read/Write Software Context Number" ),
        ( 0b011, 0b100, "c13", "c0", 0b111 )  : ( "SCXTNUM_EL2", "EL2 Read/Write Software Context Number" ),
        ( 0b011, 0b110, "c13", "c0", 0b111 )  : ( "SCXTNUM_EL3", "EL3 Read/Write Software Context Number" ),
        ( 0b011, 0b000, "c5", "c6", 0b000 )   : ( "TFSR_EL1", "Tag Fault Status Register (EL1)" ),
        ( 0b011, 0b100, "c5", "c6", 0b000 )   : ( "TFSR_EL2", "Tag Fault Status Register (EL2)" ),
        ( 0b011, 0b110, "c5", "c6", 0b000 )   : ( "TFSR_EL3", "Tag Fault Status Register (EL3)" ),
        ( 0b011, 0b000, "c5", "c6", 0b001 )   : ( "TFSRE0_EL1", "Tag Fault Status Register (EL0)." ),
        ( 0b011, 0b100, "c2", "c2", 0b000 )   : ( "VNCR_EL2", "Virtual Nested Control Register" ),
        ( 0b011, 0b100, "c2", "c6", 0b010 )   : ( "VSTCR_EL2", "Virtualization Secure Translation Control Register" ),
        ( 0b011, 0b100, "c2", "c6", 0b000 )   : ( "VSTTBR_EL2", "Virtualization Secure Translation Table Base Register" ),

        # SVE.
        ( 0b011, 0b000, "c1", "c2", 0b000 )   : ( "ZCR_EL1", "SVE Control Register (EL1)" ),
        ( 0b011, 0b100, "c1", "c2", 0b000 )   : ( "ZCR_EL2", "SVE Control Register (EL2)" ),
        ( 0b011, 0b110, "c1", "c2", 0b000 )   : ( "ZCR_EL3", "SVE Control Register (EL3)" ),

        # Activity Monitors.
        ( 0b011, 0b011, "c13", "c2", 0b001 )  : ( "AMCFGR_EL0", "Activity Monitors Configuration Register" ),
        ( 0b011, 0b011, "c13", "c2", 0b110 )  : ( "AMCG1IDR_EL0", "Activity Monitors Counter Group 1 Identification Register" ),
        ( 0b011, 0b011, "c13", "c2", 0b010 )  : ( "AMCGCR_EL0", "Activity Monitors Counter Group Configuration Register" ),
        ( 0b011, 0b011, "c13", "c2", 0b100 )  : ( "AMCNTENCLR0_EL0", "Activity Monitors Count Enable Clear Register 0" ),
        ( 0b011, 0b011, "c13", "c3", 0b000 )  : ( "AMCNTENCLR1_EL0", "Activity Monitors Count Enable Clear Register 1" ),
        ( 0b011, 0b011, "c13", "c2", 0b101 )  : ( "AMCNTENSET0_EL0", "Activity Monitors Count Enable Set Register 0" ),
        ( 0b011, 0b011, "c13", "c3", 0b001 )  : ( "AMCNTENSET1_EL0", "Activity Monitors Count Enable Set Register 1" ),
        ( 0b011, 0b011, "c13", "c2", 0b000 )  : ( "AMCR_EL0", "Activity Monitors Control Register" ),
        ( 0b011, 0b011, "c13", "c4", 0b000 )  : ( "AMEVCNTR00_EL0", "Activity Monitors Event Counter Registers 0" ),
        ( 0b011, 0b011, "c13", "c4", 0b001 )  : ( "AMEVCNTR01_EL0", "Activity Monitors Event Counter Registers 0" ),
        ( 0b011, 0b011, "c13", "c4", 0b010 )  : ( "AMEVCNTR02_EL0", "Activity Monitors Event Counter Registers 0" ),
        ( 0b011, 0b011, "c13", "c4", 0b011 )  : ( "AMEVCNTR03_EL0", "Activity Monitors Event Counter Registers 0" ),
        ( 0b011, 0b011, "c13", "c12", 0b000 ) : ( "AMEVCNTR10_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b001 ) : ( "AMEVCNTR11_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b010 ) : ( "AMEVCNTR12_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b011 ) : ( "AMEVCNTR13_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b100 ) : ( "AMEVCNTR14_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b101 ) : ( "AMEVCNTR15_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b110 ) : ( "AMEVCNTR16_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c12", 0b111 ) : ( "AMEVCNTR17_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b000 ) : ( "AMEVCNTR18_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b001 ) : ( "AMEVCNTR19_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b010 ) : ( "AMEVCNTR110_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b011 ) : ( "AMEVCNTR111_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b100 ) : ( "AMEVCNTR112_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b101 ) : ( "AMEVCNTR113_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b110 ) : ( "AMEVCNTR114_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b011, "c13", "c13", 0b111 ) : ( "AMEVCNTR115_EL0", "Activity Monitors Event Counter Registers 1" ),
        ( 0b011, 0b100, "c13", "c8", 0b000 )  : ( "AMEVCNTVOFF00_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b001 )  : ( "AMEVCNTVOFF01_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b010 )  : ( "AMEVCNTVOFF02_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b011 )  : ( "AMEVCNTVOFF03_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b100 )  : ( "AMEVCNTVOFF04_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b101 )  : ( "AMEVCNTVOFF05_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b110 )  : ( "AMEVCNTVOFF06_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c8", 0b111 )  : ( "AMEVCNTVOFF07_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b000 )  : ( "AMEVCNTVOFF08_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b001 )  : ( "AMEVCNTVOFF09_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b010 )  : ( "AMEVCNTVOFF010_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b011 )  : ( "AMEVCNTVOFF011_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b100 )  : ( "AMEVCNTVOFF012_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b101 )  : ( "AMEVCNTVOFF013_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b110 )  : ( "AMEVCNTVOFF014_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c9", 0b111 )  : ( "AMEVCNTVOFF015_EL2", "Activity Monitors Event Counter Virtual Offset Registers 0" ),
        ( 0b011, 0b100, "c13", "c10", 0b000 ) : ( "AMEVCNTVOFF10_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b001 ) : ( "AMEVCNTVOFF11_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b010 ) : ( "AMEVCNTVOFF12_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b011 ) : ( "AMEVCNTVOFF13_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b100 ) : ( "AMEVCNTVOFF14_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b101 ) : ( "AMEVCNTVOFF15_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b110 ) : ( "AMEVCNTVOFF16_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c10", 0b111 ) : ( "AMEVCNTVOFF17_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b000 ) : ( "AMEVCNTVOFF18_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b001 ) : ( "AMEVCNTVOFF19_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b010 ) : ( "AMEVCNTVOFF110_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b011 ) : ( "AMEVCNTVOFF111_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b100 ) : ( "AMEVCNTVOFF112_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b101 ) : ( "AMEVCNTVOFF113_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b110 ) : ( "AMEVCNTVOFF114_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b100, "c13", "c11", 0b111 ) : ( "AMEVCNTVOFF115_EL2", "Activity Monitors Event Counter Virtual Offset Registers 1" ),
        ( 0b011, 0b011, "c13", "c6", 0b000 )  : ( "AMEVTYPER00_EL0", "Activity Monitors Event Type Registers 0" ),
        ( 0b011, 0b011, "c13", "c6", 0b001 )  : ( "AMEVTYPER01_EL0", "Activity Monitors Event Type Registers 0" ),
        ( 0b011, 0b011, "c13", "c6", 0b010 )  : ( "AMEVTYPER02_EL0", "Activity Monitors Event Type Registers 0" ),
        ( 0b011, 0b011, "c13", "c6", 0b011 )  : ( "AMEVTYPER03_EL0", "Activity Monitors Event Type Registers 0" ),
        ( 0b011, 0b011, "c13", "c14", 0b000 ) : ( "AMEVTYPER10_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b001 ) : ( "AMEVTYPER11_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b010 ) : ( "AMEVTYPER12_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b011 ) : ( "AMEVTYPER13_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b100 ) : ( "AMEVTYPER14_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b101 ) : ( "AMEVTYPER15_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b110 ) : ( "AMEVTYPER16_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c14", 0b111 ) : ( "AMEVTYPER17_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b000 ) : ( "AMEVTYPER18_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b001 ) : ( "AMEVTYPER19_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b010 ) : ( "AMEVTYPER110_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b011 ) : ( "AMEVTYPER111_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b100 ) : ( "AMEVTYPER112_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b101 ) : ( "AMEVTYPER113_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b110 ) : ( "AMEVTYPER114_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c15", 0b111 ) : ( "AMEVTYPER115_EL0", "Activity Monitors Event Type Registers 1" ),
        ( 0b011, 0b011, "c13", "c2", 0b011 )  : ( "AMUSERENR_EL0", "Activity Monitors User Enable Register" ),

        # Reliability.
        ( 0b011, 0b000, "c12", "c1", 0b001 )  : ( "DISR_EL1", "Deferred Interrupt Status Register" ),
        ( 0b011, 0b000, "c5", "c3", 0b000 )   : ( "ERRIDR_EL1", "Error Record ID Register" ),
        ( 0b011, 0b000, "c5", "c3", 0b001 )   : ( "ERRSELR_EL1", "Error Record Select Register" ),
        ( 0b011, 0b000, "c5", "c4", 0b011 )   : ( "ERXADDR_EL1", "Selected Error Record Address Register" ),
        ( 0b011, 0b000, "c5", "c4", 0b001 )   : ( "ERXCTLR_EL1", "Selected Error Record Control Register" ),
        ( 0b011, 0b000, "c5", "c4", 0b000 )   : ( "ERXFR_EL1", "Selected Error Record Feature Register" ),
        ( 0b011, 0b000, "c5", "c5", 0b000 )   : ( "ERXMISC0_EL1", "Selected Error Record Miscellaneous Register 0" ),
        ( 0b011, 0b000, "c5", "c5", 0b001 )   : ( "ERXMISC1_EL1", "Selected Error Record Miscellaneous Register 1" ),
        ( 0b011, 0b000, "c5", "c5", 0b010 )   : ( "ERXMISC2_EL1", "Selected Error Record Miscellaneous Register 2" ),
        ( 0b011, 0b000, "c5", "c5", 0b011 )   : ( "ERXMISC3_EL1", "Selected Error Record Miscellaneous Register 3" ),
        ( 0b011, 0b000, "c5", "c4", 0b110 )   : ( "ERXPFGCDN_EL1", "Selected Pseudo-fault Generation Countdown register" ),
        ( 0b011, 0b000, "c5", "c4", 0b101 )   : ( "ERXPFGCTL_EL1", "Selected Pseudo-fault Generation Control register" ),
        ( 0b011, 0b000, "c5", "c4", 0b100 )   : ( "ERXPFGF_EL1", "Selected Pseudo-fault Generation Feature register" ),
        ( 0b011, 0b000, "c5", "c4", 0b010 )   : ( "ERXSTATUS_EL1", "Selected Error Record Primary Status Register" ),
        ( 0b011, 0b100, "c12", "c1", 0b001 )  : ( "VDISR_EL2", "Virtual Deferred Interrupt Status Register" ),
        ( 0b011, 0b100, "c5", "c2", 0b011 )   : ( "VSESR_EL2", "Virtual SError Exception Syndrome Register" ),

        # Memory partitioning.
        ( 0b011, 0b000, "c10", "c5", 0b001 )  : ( "MPAM0_EL1", "MPAM0 Register (EL1)" ),
        ( 0b011, 0b000, "c10", "c5", 0b000 )  : ( "MPAM1_EL1", "MPAM1 Register (EL1)" ),
        ( 0b011, 0b100, "c10", "c5", 0b000 )  : ( "MPAM2_EL2", "MPAM2 Register (EL2)" ),
        ( 0b011, 0b110, "c10", "c5", 0b000 )  : ( "MPAM3_EL3", "MPAM3 Register (EL3)" ),
        ( 0b011, 0b100, "c10", "c4", 0b000 )  : ( "MPAMHCR_EL2", "MPAM Hypervisor Control Register (EL2)" ),
        ( 0b011, 0b000, "c10", "c4", 0b100 )  : ( "MPAMIDR_EL1", "MPAM ID Register (EL1)" ),
        ( 0b011, 0b100, "c10", "c6", 0b000 )  : ( "MPAMVPM0_EL2", "MPAM Virtual PARTID Mapping Register 0" ),
        ( 0b011, 0b100, "c10", "c6", 0b001 )  : ( "MPAMVPM1_EL2", "MPAM Virtual PARTID Mapping Register 1" ),
        ( 0b011, 0b100, "c10", "c6", 0b010 )  : ( "MPAMVPM2_EL2", "MPAM Virtual PARTID Mapping Register 2" ),
        ( 0b011, 0b100, "c10", "c6", 0b011 )  : ( "MPAMVPM3_EL2", "MPAM Virtual PARTID Mapping Register 3" ),
        ( 0b011, 0b100, "c10", "c6", 0b100 )  : ( "MPAMVPM4_EL2", "MPAM Virtual PARTID Mapping Register 4" ),
        ( 0b011, 0b100, "c10", "c6", 0b101 )  : ( "MPAMVPM5_EL2", "MPAM Virtual PARTID Mapping Register 5" ),
        ( 0b011, 0b100, "c10", "c6", 0b110 )  : ( "MPAMVPM6_EL2", "MPAM Virtual PARTID Mapping Register 6" ),
        ( 0b011, 0b100, "c10", "c6", 0b111 )  : ( "MPAMVPM7_EL2", "MPAM Virtual PARTID Mapping Register 7" ),
        ( 0b011, 0b100, "c10", "c4", 0b001 )  : ( "MPAMVPMV_EL2", "MPAM Virtual Partition Mapping Valid Register" ),

        # Profiling.
        ( 0b011, 0b000, "c9", "c10", 0b111 )  : ( "PMBIDR_EL1", "Profiling Buffer ID Register" ),
        ( 0b011, 0b000, "c9", "c10", 0b000 )  : ( "PMBLIMITR_EL1", "Profiling Buffer Limit Address Register" ),
        ( 0b011, 0b000, "c9", "c10", 0b001 )  : ( "PMBPTR_EL1", "Profiling Buffer Write Pointer Register" ),
        ( 0b011, 0b000, "c9", "c10", 0b011 )  : ( "PMBSR_EL1", "Profiling Buffer Status/syndrome Register" ),
        ( 0b011, 0b011, "c14", "c11", 0b111 ) : ( "PMEVCNTR31_EL0", "Performance Monitors Event Count Registers" ),
        ( 0b011, 0b011, "c14", "c15", 0b111 ) : ( "PMEVTYPER31_EL0", "Performance Monitors Event Type Registers" ),
        ( 0b011, 0b000, "c9", "c14", 0b110 )  : ( "PMMIR_EL1", "Performance Monitors Machine Identification Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b000 )   : ( "PMSCR_EL1", "Statistical Profiling Control Register (EL1)" ),
        ( 0b011, 0b100, "c9", "c9", 0b000 )   : ( "PMSCR_EL2", "Statistical Profiling Control Register (EL2)" ),
        ( 0b011, 0b000, "c9", "c9", 0b101 )   : ( "PMSEVFR_EL1", "Sampling Event Filter Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b100 )   : ( "PMSFCR_EL1", "Sampling Filter Control Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b010 )   : ( "PMSICR_EL1", "Sampling Interval Counter Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b111 )   : ( "PMSIDR_EL1", "Sampling Profiling ID Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b011 )   : ( "PMSIRR_EL1", "Sampling Interval Reload Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b110 )   : ( "PMSLATFR_EL1", "Sampling Latency Filter Register" ),
        ( 0b011, 0b000, "c9", "c9", 0b001 )   : ( "PMSNEVFR_EL1", "Sampling Inverted Event Filter Register" ),

        # Pointer authentication keys.
        ( 0b011, 0b000, "c2", "c1", 0b000 )   : ( "APIAKeyLo_EL1", "Pointer Authentication Key A for Instruction (bits[63:0]) " ),
        ( 0b011, 0b000, "c2", "c1", 0b001 )   : ( "APIAKeyHi_EL1", "Pointer Authentication Key A for Instruction (bits[127:64]) " ),
        ( 0b011, 0b000, "c2", "c1", 0b010 )   : ( "APIBKeyLo_EL1", "Pointer Authentication Key B for Instruction (bits[63:0]) " ),
        ( 0b011, 0b000, "c2", "c1", 0b011 )   : ( "APIBKeyHi_EL1", "Pointer Authentication Key B for Instruction (bits[127:64]) " ),
        ( 0b011, 0b000, "c2", "c2", 0b000 )   : ( "APDAKeyLo_EL1", "Pointer Authentication Key A for Data (bits[63:0]) " ),
        ( 0b011, 0b000, "c2", "c2", 0b001 )   : ( "APDAKeyHi_EL1", "Pointer Authentication Key A for Data (bits[127:64]) " ),
        ( 0b011, 0b000, "c2", "c2", 0b010 )   : ( "APDBKeyLo_EL1", "Pointer Authentication Key B for Data (bits[63:0]) " ),
        ( 0b011, 0b000, "c2", "c2", 0b011 )   : ( "APDBKeyHi_EL1", "Pointer Authentication Key B for Data (bits[127:64]) " ),
        ( 0b011, 0b000, "c2", "c3", 0b000 )   : ( "APGAKeyLo_EL1", "Pointer Authentication Key A for Code  (bits[63:0]) " ),
        ( 0b011, 0b000, "c2", "c3", 0b001 )   : ( "APGAKeyHi_EL1", "Pointer Authentication Key A for Code (bits[127:64]) " ),

        # Debug registers.
        ( 0b011, 0b100, "c1", "c1", 0b001 )   : ( "MDCR_EL2", "Monitor Debug Configuration Register (EL2)" ),
        ( 0b011, 0b110, "c1", "c3", 0b001 )   : ( "MDCR_EL3", "Monitor Debug Configuration Register (EL3)" ),
        ( 0b011, 0b011, "c4", "c5", 0b000 )   : ( "DSPSR_EL0", "Debug Saved Program Status Register" ),
        ( 0b011, 0b011, "c4", "c5", 0b001 )   : ( "DLR_EL0", "Debug Link Register" ),
        ( 0b010, 0b000, "c0", "c0", 0b010 )   : ( "OSDTRRX_EL1", "OS Lock Data Transfer Register, Receive" ),
        ( 0b010, 0b000, "c0", "c3", 0b010 )   : ( "OSDTRTX_EL1", "OS Lock Data Transfer Register, Transmit" ),
        ( 0b010, 0b000, "c0", "c6", 0b010 )   : ( "OSECCR_EL1", "OS Lock Exception Catch Control Register" ),
        ( 0b010, 0b011, "c0", "c4", 0b000 )   : ( "DBGDTR_EL0", "Debug Data Transfer Register, half-duplex" ),
        ( 0b010, 0b011, "c0", "c5", 0b000 )   : ( "DBGDTRTX_EL0", "Debug Data Transfer Register, Transmit",
                                                  "DBGDTRRX_EL0", "Debug Data Transfer Register, Receive" ),
        ( 0b010, 0b100, "c0", "c7", 0b000 )   : ( "DBGVCR32_EL2", "Debug Vector Catch Register" ),
        ( 0b010, 0b000, "c0", "c0", 0b100 )   : ( "DBGBVR0_EL1", "Debug Breakpoint Value Register 0" ),
        ( 0b010, 0b000, "c0", "c1", 0b100 )   : ( "DBGBVR1_EL1", "Debug Breakpoint Value Register 1" ),
        ( 0b010, 0b000, "c0", "c2", 0b100 )   : ( "DBGBVR2_EL1", "Debug Breakpoint Value Register 2" ),
        ( 0b010, 0b000, "c0", "c3", 0b100 )   : ( "DBGBVR3_EL1", "Debug Breakpoint Value Register 3" ),
        ( 0b010, 0b000, "c0", "c4", 0b100 )   : ( "DBGBVR4_EL1", "Debug Breakpoint Value Register 4" ),
        ( 0b010, 0b000, "c0", "c5", 0b100 )   : ( "DBGBVR5_EL1", "Debug Breakpoint Value Register 5" ),
        ( 0b010, 0b000, "c0", "c6", 0b100 )   : ( "DBGBVR6_EL1", "Debug Breakpoint Value Register 6" ),
        ( 0b010, 0b000, "c0", "c7", 0b100 )   : ( "DBGBVR7_EL1", "Debug Breakpoint Value Register 7" ),
        ( 0b010, 0b000, "c0", "c8", 0b100 )   : ( "DBGBVR8_EL1", "Debug Breakpoint Value Register 8" ),
        ( 0b010, 0b000, "c0", "c9", 0b100 )   : ( "DBGBVR9_EL1", "Debug Breakpoint Value Register 9" ),
        ( 0b010, 0b000, "c0", "c10", 0b100 )  : ( "DBGBVR10_EL1", "Debug Breakpoint Value Registers 10" ),
        ( 0b010, 0b000, "c0", "c11", 0b100 )  : ( "DBGBVR11_EL1", "Debug Breakpoint Value Registers 11" ),
        ( 0b010, 0b000, "c0", "c12", 0b100 )  : ( "DBGBVR12_EL1", "Debug Breakpoint Value Registers 12" ),
        ( 0b010, 0b000, "c0", "c13", 0b100 )  : ( "DBGBVR13_EL1", "Debug Breakpoint Value Registers 13" ),
        ( 0b010, 0b000, "c0", "c14", 0b100 )  : ( "DBGBVR14_EL1", "Debug Breakpoint Value Registers 14" ),
        ( 0b010, 0b000, "c0", "c15", 0b100 )  : ( "DBGBVR15_EL1", "Debug Breakpoint Value Registers 15" ),
        ( 0b010, 0b000, "c0", "c0", 0b101 )   : ( "DBGBCR0_EL1", "Debug Breakpoint Control Register 0" ),
        ( 0b010, 0b000, "c0", "c1", 0b101 )   : ( "DBGBCR1_EL1", "Debug Breakpoint Control Register 1" ),
        ( 0b010, 0b000, "c0", "c2", 0b101 )   : ( "DBGBCR2_EL1", "Debug Breakpoint Control Register 2" ),
        ( 0b010, 0b000, "c0", "c3", 0b101 )   : ( "DBGBCR3_EL1", "Debug Breakpoint Control Register 3" ),
        ( 0b010, 0b000, "c0", "c4", 0b101 )   : ( "DBGBCR4_EL1", "Debug Breakpoint Control Register 4" ),
        ( 0b010, 0b000, "c0", "c5", 0b101 )   : ( "DBGBCR5_EL1", "Debug Breakpoint Control Register 5" ),
        ( 0b010, 0b000, "c0", "c6", 0b101 )   : ( "DBGBCR6_EL1", "Debug Breakpoint Control Register 6" ),
        ( 0b010, 0b000, "c0", "c7", 0b101 )   : ( "DBGBCR7_EL1", "Debug Breakpoint Control Register 7" ),
        ( 0b010, 0b000, "c0", "c8", 0b101 )   : ( "DBGBCR8_EL1", "Debug Breakpoint Control Register 8" ),
        ( 0b010, 0b000, "c0", "c9", 0b101 )   : ( "DBGBCR9_EL1", "Debug Breakpoint Control Register 9" ),
        ( 0b010, 0b000, "c0", "c10", 0b101 )  : ( "DBGBCR10_EL1", "Debug Breakpoint Control Register 10" ),
        ( 0b010, 0b000, "c0", "c11", 0b101 )  : ( "DBGBCR11_EL1", "Debug Breakpoint Control Register 11" ),
        ( 0b010, 0b000, "c0", "c12", 0b101 )  : ( "DBGBCR12_EL1", "Debug Breakpoint Control Register 12" ),
        ( 0b010, 0b000, "c0", "c13", 0b101 )  : ( "DBGBCR13_EL1", "Debug Breakpoint Control Register 13" ),
        ( 0b010, 0b000, "c0", "c14", 0b101 )  : ( "DBGBCR14_EL1", "Debug Breakpoint Control Register 14" ),
        ( 0b010, 0b000, "c0", "c15", 0b101 )  : ( "DBGBCR15_EL1", "Debug Breakpoint Control Register 15" ),
        ( 0b010, 0b000, "c0", "c0", 0b110 )   : ( "DBGWVR0_EL1", "Debug Watchpoint Value Register 0" ),
        ( 0b010, 0b000, "c0", "c1", 0b110 )   : ( "DBGWVR1_EL1", "Debug Watchpoint Value Register 1" ),
        ( 0b010, 0b000, "c0", "c2", 0b110 )   : ( "DBGWVR2_EL1", "Debug Watchpoint Value Register 2" ),
        ( 0b010, 0b000, "c0", "c3", 0b110 )   : ( "DBGWVR3_EL1", "Debug Watchpoint Value Register 3" ),
        ( 0b010, 0b000, "c0", "c4", 0b110 )   : ( "DBGWVR4_EL1", "Debug Watchpoint Value Register 4" ),
        ( 0b010, 0b000, "c0", "c5", 0b110 )   : ( "DBGWVR5_EL1", "Debug Watchpoint Value Register 5" ),
        ( 0b010, 0b000, "c0", "c6", 0b110 )   : ( "DBGWVR6_EL1", "Debug Watchpoint Value Register 6" ),
        ( 0b010, 0b000, "c0", "c7", 0b110 )   : ( "DBGWVR7_EL1", "Debug Watchpoint Value Register 7" ),
        ( 0b010, 0b000, "c0", "c8", 0b110 )   : ( "DBGWVR8_EL1", "Debug Watchpoint Value Register 8" ),
        ( 0b010, 0b000, "c0", "c9", 0b110 )   : ( "DBGWVR9_EL1", "Debug Watchpoint Value Register 9" ),
        ( 0b010, 0b000, "c0", "c10", 0b110 )  : ( "DBGWVR10_EL1", "Debug Watchpoint Value Register 10" ),
        ( 0b010, 0b000, "c0", "c11", 0b110 )  : ( "DBGWVR11_EL1", "Debug Watchpoint Value Register 11" ),
        ( 0b010, 0b000, "c0", "c12", 0b110 )  : ( "DBGWVR12_EL1", "Debug Watchpoint Value Register 12" ),
        ( 0b010, 0b000, "c0", "c13", 0b110 )  : ( "DBGWVR13_EL1", "Debug Watchpoint Value Register 13" ),
        ( 0b010, 0b000, "c0", "c14", 0b110 )  : ( "DBGWVR14_EL1", "Debug Watchpoint Value Register 14" ),
        ( 0b010, 0b000, "c0", "c15", 0b110 )  : ( "DBGWVR15_EL1", "Debug Watchpoint Value Register 15" ),
        ( 0b010, 0b000, "c0", "c0", 0b111 )   : ( "DBGWCR0_EL1", "Debug Watchpoint Control Register 0" ),
        ( 0b010, 0b000, "c0", "c1", 0b111 )   : ( "DBGWCR1_EL1", "Debug Watchpoint Control Register 1" ),
        ( 0b010, 0b000, "c0", "c2", 0b111 )   : ( "DBGWCR2_EL1", "Debug Watchpoint Control Register 2" ),
        ( 0b010, 0b000, "c0", "c3", 0b111 )   : ( "DBGWCR3_EL1", "Debug Watchpoint Control Register 3" ),
        ( 0b010, 0b000, "c0", "c4", 0b111 )   : ( "DBGWCR4_EL1", "Debug Watchpoint Control Register 4" ),
        ( 0b010, 0b000, "c0", "c5", 0b111 )   : ( "DBGWCR5_EL1", "Debug Watchpoint Control Register 5" ),
        ( 0b010, 0b000, "c0", "c6", 0b111 )   : ( "DBGWCR6_EL1", "Debug Watchpoint Control Register 6" ),
        ( 0b010, 0b000, "c0", "c7", 0b111 )   : ( "DBGWCR7_EL1", "Debug Watchpoint Control Register 7" ),
        ( 0b010, 0b000, "c0", "c8", 0b111 )   : ( "DBGWCR8_EL1", "Debug Watchpoint Control Register 8" ),
        ( 0b010, 0b000, "c0", "c9", 0b111 )   : ( "DBGWCR9_EL1", "Debug Watchpoint Control Register 9" ),
        ( 0b010, 0b000, "c0", "c10", 0b111 )  : ( "DBGWCR10_EL1", "Debug Watchpoint Control Register 10" ),
        ( 0b010, 0b000, "c0", "c11", 0b111 )  : ( "DBGWCR11_EL1", "Debug Watchpoint Control Register 11" ),
        ( 0b010, 0b000, "c0", "c12", 0b111 )  : ( "DBGWCR12_EL1", "Debug Watchpoint Control Register 12" ),
        ( 0b010, 0b000, "c0", "c13", 0b111 )  : ( "DBGWCR13_EL1", "Debug Watchpoint Control Register 13" ),
        ( 0b010, 0b000, "c0", "c14", 0b111 )  : ( "DBGWCR14_EL1", "Debug Watchpoint Control Register 14" ),
        ( 0b010, 0b000, "c0", "c15", 0b111 )  : ( "DBGWCR15_EL1", "Debug Watchpoint Control Register 15" ),
        ( 0b010, 0b011, "c0", "c1", 0b000 )   : ( "MDCCSR_EL0", "Monitor DCC Status Register" ),
        ( 0b010, 0b000, "c0", "c2", 0b000 )   : ( "MDCCINT_EL1", "Monitor DCC Interrupt Enable Register" ),
        ( 0b010, 0b000, "c0", "c2", 0b010 )   : ( "MDSCR_EL1", "Monitor Debug System Control Register" ),
        ( 0b010, 0b000, "c1", "c0", 0b000 )   : ( "MDRAR_EL1", "Monitor Debug ROM Address Register" ),
        ( 0b010, 0b000, "c1", "c0", 0b100 )   : ( "OSLAR_EL1", "OS Lock Access Register" ),
        ( 0b010, 0b000, "c1", "c1", 0b100 )   : ( "OSLSR_EL1", "OS Lock Status Register" ),
        ( 0b010, 0b000, "c1", "c3", 0b100 )   : ( "OSDLR_EL1", "OS Double Lock Register" ),
        ( 0b010, 0b000, "c1", "c4", 0b100 )   : ( "DBGPRCR_EL1", "Debug Power Control Register" ),
        ( 0b010, 0b000, "c7", "c8", 0b110 )   : ( "DBGCLAIMSET_EL1", "Debug Claim Tag Set register" ),
        ( 0b010, 0b000, "c7", "c9", 0b110 )   : ( "DBGCLAIMCLR_EL1", "Debug Claim Tag Clear register" ),
        ( 0b010, 0b000, "c7", "c14", 0b110 )  : ( "DBGAUTHSTATUS_EL1", "Debug Authentication Status register" ),
        ( 0b011, 0b100, "c1", "c3", 0b001 )   : ( "SDER32_EL2", "AArch32 Secure Debug Enable Register" ),
        ( 0b011, 0b110, "c1", "c1", 0b001 )   : ( "SDER32_EL3", "AArch32 Secure Debug Enable Register" ),
        ( 0b011, 0b000, "c1", "c2", 0b001 )   : ( "TRFCR_EL1", "Trace Filter Control Register (EL1)" ),
        ( 0b011, 0b100, "c1", "c2", 0b001 )   : ( "TRFCR_EL2", "Trace Filter Control Register (EL2)" ),

        # Limited ordering regions.
        ( 0b011, 0b000, "c10", "c4", 0b011 )  : ( "LORC_EL1", "LORegion Control (EL1)" ),
        ( 0b011, 0b000, "c10", "c4", 0b000 )  : ( "LORSA_EL1", "LORegion Start Address (EL1)" ),
        ( 0b011, 0b000, "c10", "c4", 0b001 )  : ( "LOREA_EL1", "LORegion End Address (EL1)" ),
        ( 0b011, 0b000, "c10", "c4", 0b010 )  : ( "LORN_EL1", "LORegion Number (EL1)" ),
        ( 0b011, 0b000, "c10", "c4", 0b111 )  : ( "LORID_EL1", "LORegionID (EL1)" ),

        # Performance monitor registers.
        ( 0b011, 0b011, "c14", "c15", 0b111 ) : ( "PMCCFILTR_EL0", "Performance Monitors Cycle Count Filter Register" ),
        ( 0b011, 0b011, "c9", "c13", 0b000 )  : ( "PMCCNTR_EL0", "Performance Monitors Cycle Count Register" ),
        ( 0b011, 0b011, "c9", "c12", 0b110 )  : ( "PMCEID0_EL0", "Performance Monitors Common Event Identification register 0" ),
        ( 0b011, 0b011, "c9", "c12", 0b111 )  : ( "PMCEID1_EL0", "Performance Monitors Common Event Identification register 1" ),
        ( 0b011, 0b011, "c9", "c12", 0b010 )  : ( "PMCNTENCLR_EL0", "Performance Monitors Count Enable Clear register" ),
        ( 0b011, 0b011, "c9", "c12", 0b001 )  : ( "PMCNTENSET_EL0", "Performance Monitors Count Enable Set register" ),
        ( 0b011, 0b011, "c9", "c12", 0b000 )  : ( "PMCR_EL0", "Performance Monitors Control Register" ),
        ( 0b011, 0b011, "c14", "c8", 0b000 )  : ( "PMEVCNTR0_EL0", "Performance Monitors Event Count Register 0" ),
        ( 0b011, 0b011, "c14", "c8", 0b001 )  : ( "PMEVCNTR1_EL0", "Performance Monitors Event Count Register 1" ),
        ( 0b011, 0b011, "c14", "c8", 0b010 )  : ( "PMEVCNTR2_EL0", "Performance Monitors Event Count Register 2" ),
        ( 0b011, 0b011, "c14", "c8", 0b011 )  : ( "PMEVCNTR3_EL0", "Performance Monitors Event Count Register 3" ),
        ( 0b011, 0b011, "c14", "c8", 0b100 )  : ( "PMEVCNTR4_EL0", "Performance Monitors Event Count Register 4" ),
        ( 0b011, 0b011, "c14", "c8", 0b101 )  : ( "PMEVCNTR5_EL0", "Performance Monitors Event Count Register 5" ),
        ( 0b011, 0b011, "c14", "c8", 0b110 )  : ( "PMEVCNTR6_EL0", "Performance Monitors Event Count Register 6" ),
        ( 0b011, 0b011, "c14", "c8", 0b111 )  : ( "PMEVCNTR7_EL0", "Performance Monitors Event Count Register 7" ),
        ( 0b011, 0b011, "c14", "c9", 0b000 )  : ( "PMEVCNTR8_EL0", "Performance Monitors Event Count Register 8" ),
        ( 0b011, 0b011, "c14", "c9", 0b001 )  : ( "PMEVCNTR9_EL0", "Performance Monitors Event Count Register 9" ),
        ( 0b011, 0b011, "c14", "c9", 0b010 )  : ( "PMEVCNTR10_EL0", "Performance Monitors Event Count Register 10" ),
        ( 0b011, 0b011, "c14", "c9", 0b011 )  : ( "PMEVCNTR11_EL0", "Performance Monitors Event Count Register 11" ),
        ( 0b011, 0b011, "c14", "c9", 0b100 )  : ( "PMEVCNTR12_EL0", "Performance Monitors Event Count Register 12" ),
        ( 0b011, 0b011, "c14", "c9", 0b101 )  : ( "PMEVCNTR13_EL0", "Performance Monitors Event Count Register 13" ),
        ( 0b011, 0b011, "c14", "c9", 0b110 )  : ( "PMEVCNTR14_EL0", "Performance Monitors Event Count Register 14" ),
        ( 0b011, 0b011, "c14", "c9", 0b111 )  : ( "PMEVCNTR15_EL0", "Performance Monitors Event Count Register 15" ),
        ( 0b011, 0b011, "c14", "c10", 0b000 ) : ( "PMEVCNTR16_EL0", "Performance Monitors Event Count Register 16" ),
        ( 0b011, 0b011, "c14", "c10", 0b001 ) : ( "PMEVCNTR17_EL0", "Performance Monitors Event Count Register 17" ),
        ( 0b011, 0b011, "c14", "c10", 0b010 ) : ( "PMEVCNTR18_EL0", "Performance Monitors Event Count Register 18" ),
        ( 0b011, 0b011, "c14", "c10", 0b011 ) : ( "PMEVCNTR19_EL0", "Performance Monitors Event Count Register 19" ),
        ( 0b011, 0b011, "c14", "c10", 0b100 ) : ( "PMEVCNTR20_EL0", "Performance Monitors Event Count Register 20" ),
        ( 0b011, 0b011, "c14", "c10", 0b101 ) : ( "PMEVCNTR21_EL0", "Performance Monitors Event Count Register 21" ),
        ( 0b011, 0b011, "c14", "c10", 0b110 ) : ( "PMEVCNTR22_EL0", "Performance Monitors Event Count Register 22" ),
        ( 0b011, 0b011, "c14", "c10", 0b111 ) : ( "PMEVCNTR23_EL0", "Performance Monitors Event Count Register 23" ),
        ( 0b011, 0b011, "c14", "c11", 0b000 ) : ( "PMEVCNTR24_EL0", "Performance Monitors Event Count Register 24" ),
        ( 0b011, 0b011, "c14", "c11", 0b001 ) : ( "PMEVCNTR25_EL0", "Performance Monitors Event Count Register 25" ),
        ( 0b011, 0b011, "c14", "c11", 0b010 ) : ( "PMEVCNTR26_EL0", "Performance Monitors Event Count Register 26" ),
        ( 0b011, 0b011, "c14", "c11", 0b011 ) : ( "PMEVCNTR27_EL0", "Performance Monitors Event Count Register 27" ),
        ( 0b011, 0b011, "c14", "c11", 0b100 ) : ( "PMEVCNTR28_EL0", "Performance Monitors Event Count Register 28" ),
        ( 0b011, 0b011, "c14", "c11", 0b101 ) : ( "PMEVCNTR29_EL0", "Performance Monitors Event Count Register 29" ),
        ( 0b011, 0b011, "c14", "c11", 0b110 ) : ( "PMEVCNTR30_EL0", "Performance Monitors Event Count Register 30" ),
        ( 0b011, 0b011, "c14", "c12", 0b000 ) : ( "PMEVTYPER0_EL0", "Performance Monitors Event Type Register 0" ),
        ( 0b011, 0b011, "c14", "c12", 0b001 ) : ( "PMEVTYPER1_EL0", "Performance Monitors Event Type Register 1" ),
        ( 0b011, 0b011, "c14", "c12", 0b010 ) : ( "PMEVTYPER2_EL0", "Performance Monitors Event Type Register 2" ),
        ( 0b011, 0b011, "c14", "c12", 0b011 ) : ( "PMEVTYPER3_EL0", "Performance Monitors Event Type Register 3" ),
        ( 0b011, 0b011, "c14", "c12", 0b100 ) : ( "PMEVTYPER4_EL0", "Performance Monitors Event Type Register 4" ),
        ( 0b011, 0b011, "c14", "c12", 0b101 ) : ( "PMEVTYPER5_EL0", "Performance Monitors Event Type Register 5" ),
        ( 0b011, 0b011, "c14", "c12", 0b110 ) : ( "PMEVTYPER6_EL0", "Performance Monitors Event Type Register 6" ),
        ( 0b011, 0b011, "c14", "c12", 0b111 ) : ( "PMEVTYPER7_EL0", "Performance Monitors Event Type Register 7" ),
        ( 0b011, 0b011, "c14", "c13", 0b000 ) : ( "PMEVTYPER8_EL0", "Performance Monitors Event Type Register 8" ),
        ( 0b011, 0b011, "c14", "c13", 0b001 ) : ( "PMEVTYPER9_EL0", "Performance Monitors Event Type Register 9" ),
        ( 0b011, 0b011, "c14", "c13", 0b010 ) : ( "PMEVTYPER10_EL0", "Performance Monitors Event Type Register 10" ),
        ( 0b011, 0b011, "c14", "c13", 0b011 ) : ( "PMEVTYPER11_EL0", "Performance Monitors Event Type Register 11" ),
        ( 0b011, 0b011, "c14", "c13", 0b100 ) : ( "PMEVTYPER12_EL0", "Performance Monitors Event Type Register 12" ),
        ( 0b011, 0b011, "c14", "c13", 0b101 ) : ( "PMEVTYPER13_EL0", "Performance Monitors Event Type Register 13" ),
        ( 0b011, 0b011, "c14", "c13", 0b110 ) : ( "PMEVTYPER14_EL0", "Performance Monitors Event Type Register 14" ),
        ( 0b011, 0b011, "c14", "c13", 0b111 ) : ( "PMEVTYPER15_EL0", "Performance Monitors Event Type Register 15" ),
        ( 0b011, 0b011, "c14", "c14", 0b000 ) : ( "PMEVTYPER16_EL0", "Performance Monitors Event Type Register 16" ),
        ( 0b011, 0b011, "c14", "c14", 0b001 ) : ( "PMEVTYPER17_EL0", "Performance Monitors Event Type Register 17" ),
        ( 0b011, 0b011, "c14", "c14", 0b010 ) : ( "PMEVTYPER18_EL0", "Performance Monitors Event Type Register 18" ),
        ( 0b011, 0b011, "c14", "c14", 0b011 ) : ( "PMEVTYPER19_EL0", "Performance Monitors Event Type Register 19" ),
        ( 0b011, 0b011, "c14", "c14", 0b100 ) : ( "PMEVTYPER20_EL0", "Performance Monitors Event Type Register 20" ),
        ( 0b011, 0b011, "c14", "c14", 0b101 ) : ( "PMEVTYPER21_EL0", "Performance Monitors Event Type Register 21" ),
        ( 0b011, 0b011, "c14", "c14", 0b110 ) : ( "PMEVTYPER22_EL0", "Performance Monitors Event Type Register 22" ),
        ( 0b011, 0b011, "c14", "c14", 0b111 ) : ( "PMEVTYPER23_EL0", "Performance Monitors Event Type Register 23" ),
        ( 0b011, 0b011, "c14", "c15", 0b000 ) : ( "PMEVTYPER24_EL0", "Performance Monitors Event Type Register 24" ),
        ( 0b011, 0b011, "c14", "c15", 0b001 ) : ( "PMEVTYPER25_EL0", "Performance Monitors Event Type Register 25" ),
        ( 0b011, 0b011, "c14", "c15", 0b010 ) : ( "PMEVTYPER26_EL0", "Performance Monitors Event Type Register 26" ),
        ( 0b011, 0b011, "c14", "c15", 0b011 ) : ( "PMEVTYPER27_EL0", "Performance Monitors Event Type Register 27" ),
        ( 0b011, 0b011, "c14", "c15", 0b100 ) : ( "PMEVTYPER28_EL0", "Performance Monitors Event Type Register 28" ),
        ( 0b011, 0b011, "c14", "c15", 0b101 ) : ( "PMEVTYPER29_EL0", "Performance Monitors Event Type Register 29" ),
        ( 0b011, 0b011, "c14", "c15", 0b110 ) : ( "PMEVTYPER30_EL0", "Performance Monitors Event Type Register 30" ),
        ( 0b011, 0b000, "c9", "c14", 0b010 )  : ( "PMINTENCLR_EL1", "Performance Monitors Interrupt Enable Clear register" ),
        ( 0b011, 0b000, "c9", "c14", 0b001 )  : ( "PMINTENSET_EL1", "Performance Monitors Interrupt Enable Set register" ),
        ( 0b011, 0b011, "c9", "c12", 0b011 )  : ( "PMOVSCLR_EL0", "Performance Monitors Overflow Flag Status Clear Register" ),
        ( 0b011, 0b011, "c9", "c14", 0b011 )  : ( "PMOVSSET_EL0", "Performance Monitors Overflow Flag Status Set register" ),
        ( 0b011, 0b011, "c9", "c12", 0b101 )  : ( "PMSELR_EL0", "Performance Monitors Event Counter Selection Register" ),
        ( 0b011, 0b011, "c9", "c12", 0b100 )  : ( "PMSWINC_EL0", "Performance Monitors Software Increment register" ),
        ( 0b011, 0b011, "c9", "c14", 0b000 )  : ( "PMUSERENR_EL0", "Performance Monitors User Enable Register" ),
        ( 0b011, 0b011, "c9", "c13", 0b010 )  : ( "PMXEVCNTR_EL0", "Performance Monitors Selected Event Count Register" ),
        ( 0b011, 0b011, "c9", "c13", 0b001 )  : ( "PMXEVTYPER_EL0", "Performance Monitors Selected Event Type Register" ),

        # Generic Timer registers.
        ( 0b011, 0b011, "c14", "c0", 0b000 )  : ( "CNTFRQ_EL0", "Counter-timer Frequency register" ),
        ( 0b011, 0b100, "c14", "c1", 0b000 )  : ( "CNTHCTL_EL2", "Counter-timer Hypervisor Control register" ),
        ( 0b011, 0b100, "c14", "c2", 0b001 )  : ( "CNTHP_CTL_EL2", "Counter-timer Hypervisor Physical Timer Control register" ),
        ( 0b011, 0b100, "c14", "c2", 0b010 )  : ( "CNTHP_CVAL_EL2", "Counter-timer Hypervisor Physical Timer CompareValue register" ),
        ( 0b011, 0b100, "c14", "c2", 0b000 )  : ( "CNTHP_TVAL_EL2", "Counter-timer Hypervisor Physical Timer TimerValue register" ),
        ( 0b011, 0b100, "c14", "c3", 0b000 )  : ( "CNTHV_TVAL_EL2", "Counter-timer Virtual Timer TimerValue register (EL2)" ),
        ( 0b011, 0b100, "c14", "c3", 0b001 )  : ( "CNTHV_CTL_EL2", "Counter-timer Virtual Timer Control register (EL2)" ),
        ( 0b011, 0b100, "c14", "c3", 0b010 )  : ( "CNTHV_CVAL_EL2", "Counter-timer Virtual Timer CompareValue register (EL2)" ),
        ( 0b011, 0b000, "c14", "c1", 0b000 )  : ( "CNTKCTL_EL1", "Counter-timer Hypervisor Control register" ),
        ( 0b011, 0b101, "c14", "c1", 0b000 )  : ( "CNTKCTL_EL12", "Counter-timer Kernel Control register" ),
        ( 0b011, 0b011, "c14", "c2", 0b001 )  : ( "CNTP_CTL_EL0", "Counter-timer Hypervisor Physical Timer Control register" ),
        ( 0b011, 0b101, "c14", "c2", 0b001 )  : ( "CNTP_CTL_EL02", "Counter-timer Physical Timer Control register" ),
        ( 0b011, 0b011, "c14", "c2", 0b010 )  : ( "CNTP_CVAL_EL0", "Counter-timer Physical Timer CompareValue register" ),
        ( 0b011, 0b101, "c14", "c2", 0b010 )  : ( "CNTP_CVAL_EL02", "Counter-timer Physical Timer CompareValue register" ),
        ( 0b011, 0b011, "c14", "c2", 0b000 )  : ( "CNTP_TVAL_EL0", "Counter-timer Physical Timer TimerValue register" ),
        ( 0b011, 0b101, "c14", "c2", 0b000 )  : ( "CNTP_TVAL_EL02", "Counter-timer Physical Timer TimerValue register" ),
        ( 0b011, 0b011, "c14", "c0", 0b001 )  : ( "CNTPCT_EL0", "Counter-timer Physical Count register" ),
        ( 0b011, 0b111, "c14", "c2", 0b001 )  : ( "CNTPS_CTL_EL1", "Counter-timer Physical Secure Timer Control register" ),
        ( 0b011, 0b111, "c14", "c2", 0b010 )  : ( "CNTPS_CVAL_EL1", "Counter-timer Physical Secure Timer CompareValue register" ),
        ( 0b011, 0b111, "c14", "c2", 0b000 )  : ( "CNTPS_TVAL_EL1", "Counter-timer Physical Secure Timer TimerValue register" ),
        ( 0b011, 0b011, "c14", "c3", 0b001 )  : ( "CNTV_CTL_EL0", "Counter-timer Virtual Timer Control register (EL2)" ),
        ( 0b011, 0b101, "c14", "c3", 0b001 )  : ( "CNTV_CTL_EL02", "Counter-timer Virtual Timer Control register" ),
        ( 0b011, 0b011, "c14", "c3", 0b010 )  : ( "CNTV_CVAL_EL0", "Counter-timer Virtual Timer CompareValue register" ),
        ( 0b011, 0b101, "c14", "c3", 0b010 )  : ( "CNTV_CVAL_EL02", "Counter-timer Virtual Timer CompareValue register" ),
        ( 0b011, 0b011, "c14", "c3", 0b000 )  : ( "CNTV_TVAL_EL0", "Counter-timer Virtual Timer TimerValue register" ),
        ( 0b011, 0b101, "c14", "c3", 0b000 )  : ( "CNTV_TVAL_EL02", "Counter-timer Virtual Timer TimerValue register" ),
        ( 0b011, 0b011, "c14", "c0", 0b010 )  : ( "CNTVCT_EL0", "Counter-timer Virtual Count register" ),
        ( 0b011, 0b100, "c14", "c0", 0b011 )  : ( "CNTVOFF_EL2", "Counter-timer Virtual Offset register" ),
        ( 0b011, 0b100, "c14", "c5", 0b001 )  : ( "CNTHPS_CTL_EL2", "Counter-timer Secure Physical Timer Control register (EL2)" ),
        ( 0b011, 0b100, "c14", "c5", 0b010 )  : ( "CNTHPS_CVAL_EL2", "Counter-timer Secure Physical Timer CompareValue register (EL2)" ),
        ( 0b011, 0b100, "c14", "c5", 0b000 )  : ( "CNTHPS_TVAL_EL2", "Counter-timer Secure Physical Timer TimerValue register (EL2)" ),
        ( 0b011, 0b100, "c14", "c4", 0b001 )  : ( "CNTHVS_CTL_EL2", "Counter-timer Secure Virtual Timer Control register (EL2)" ),
        ( 0b011, 0b100, "c14", "c4", 0b010 )  : ( "CNTHVS_CVAL_EL2", "Counter-timer Secure Virtual Timer CompareValue register (EL2)" ),
        ( 0b011, 0b100, "c14", "c4", 0b000 )  : ( "CNTHVS_TVAL_EL2", "Counter-timer Secure Virtual Timer TimerValue register (EL2)" ),
        ( 0b011, 0b011, "c14", "c0", 0b101 )  : ( "CNTPCTSS_EL0", "Counter-timer Self-Synchronized Physical Count register" ),
        ( 0b011, 0b100, "c14", "c0", 0b110 )  : ( "CNTPOFF_EL2", "Counter-timer Physical Offset register" ),
        ( 0b011, 0b011, "c14", "c0", 0b110 )  : ( "CNTVCTSS_EL0", "Counter-timer Self-Synchronized Virtual Count register" ),

        # Generic Interrupt Controller CPU interface registers.
        ( 0b011, 0b000, "c12", "c8", 0b100 )  : ( "ICC_AP0R0_EL1", "Interrupt Controller Active Priorities Group 0 Register 0" ),
        ( 0b011, 0b000, "c12", "c8", 0b101 )  : ( "ICC_AP0R1_EL1", "Interrupt Controller Active Priorities Group 0 Register 1" ),
        ( 0b011, 0b000, "c12", "c8", 0b110 )  : ( "ICC_AP0R2_EL1", "Interrupt Controller Active Priorities Group 0 Register 2" ),
        ( 0b011, 0b000, "c12", "c8", 0b111 )  : ( "ICC_AP0R3_EL1", "Interrupt Controller Active Priorities Group 0 Register 3" ),
        ( 0b011, 0b000, "c12", "c9", 0b000 )  : ( "ICC_AP1R0_EL1", "Interrupt Controller Active Priorities Group 1 Register 0" ),
        ( 0b011, 0b000, "c12", "c9", 0b001 )  : ( "ICC_AP1R1_EL1", "Interrupt Controller Active Priorities Group 1 Register 1" ),
        ( 0b011, 0b000, "c12", "c9", 0b010 )  : ( "ICC_AP1R2_EL1", "Interrupt Controller Active Priorities Group 1 Register 2" ),
        ( 0b011, 0b000, "c12", "c9", 0b011 )  : ( "ICC_AP1R3_EL1", "Interrupt Controller Active Priorities Group 1 Register 3" ),
        ( 0b011, 0b000, "c12", "c11", 0b110 ) : ( "ICC_ASGI1R_EL1", "Interrupt Controller Alias Software Generated Interrupt Group 1 Register" ),
        ( 0b011, 0b000, "c12", "c8", 0b011 )  : ( "ICC_BPR0_EL1", "Interrupt Controller Binary Point Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b011 ) : ( "ICC_BPR1_EL1", "Interrupt Controller Binary Point Register 1" ),
        ( 0b011, 0b000, "c12", "c12", 0b100 ) : ( "ICC_CTLR_EL1", "Interrupt Controller Virtual Control Register" ),
        ( 0b011, 0b110, "c12", "c12", 0b100 ) : ( "ICC_CTLR_EL3", "Interrupt Controller Control Register (EL3)" ),
        ( 0b011, 0b000, "c12", "c11", 0b001 ) : ( "ICC_DIR_EL1", "Interrupt Controller Deactivate Virtual Interrupt Register" ),
        ( 0b011, 0b000, "c12", "c8", 0b001 )  : ( "ICC_EOIR0_EL1", "Interrupt Controller End Of Interrupt Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b001 ) : ( "ICC_EOIR1_EL1", "Interrupt Controller End Of Interrupt Register 1" ),
        ( 0b011, 0b000, "c12", "c8", 0b010 )  : ( "ICC_HPPIR0_EL1", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b010 ) : ( "ICC_HPPIR1_EL1", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 1" ),
        ( 0b011, 0b000, "c12", "c8", 0b000 )  : ( "ICC_IAR0_EL1", "Interrupt Controller Virtual Interrupt Acknowledge Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b000 ) : ( "ICC_IAR1_EL1", "Interrupt Controller Interrupt Acknowledge Register 1" ),
        ( 0b011, 0b000, "c12", "c12", 0b110 ) : ( "ICC_IGRPEN0_EL1", "Interrupt Controller Virtual Interrupt Group 0 Enable register" ),
        ( 0b011, 0b000, "c12", "c12", 0b111 ) : ( "ICC_IGRPEN1_EL1", "Interrupt Controller Interrupt Group 1 Enable register" ),
        ( 0b011, 0b110, "c12", "c12", 0b111 ) : ( "ICC_IGRPEN1_EL3", "Interrupt Controller Interrupt Group 1 Enable register (EL3)" ),
        ( 0b011, 0b000, "c4", "c6", 0b000 )   : ( "ICC_PMR_EL1", "Interrupt Controller Interrupt Priority Mask Register" ),
        ( 0b011, 0b000, "c12", "c11", 0b011 ) : ( "ICC_RPR_EL1", "Interrupt Controller Running Priority Register" ), # Not defined in 8.2 specifications.
        ( 0b011, 0b000, "c12", "c11", 0b000 ) : ( "ICC_SEIEN_EL1", "Interrupt Controller System Error Interrupt Enable Register" ),
        ( 0b011, 0b000, "c12", "c11", 0b111 ) : ( "ICC_SGI0R_EL1", "Interrupt Controller Software Generated Interrupt Group 0 Register" ),
        ( 0b011, 0b000, "c12", "c11", 0b101 ) : ( "ICC_SGI1R_EL1", "Interrupt Controller Software Generated Interrupt Group 1 Register" ),
        ( 0b011, 0b000, "c12", "c12", 0b101 ) : ( "ICC_SRE_EL1", "Interrupt Controller System Register Enable register (EL1)" ),
        ( 0b011, 0b100, "c12", "c9", 0b101 )  : ( "ICC_SRE_EL2", "Interrupt Controller System Register Enable register (EL2)" ),
        ( 0b011, 0b110, "c12", "c12", 0b101 ) : ( "ICC_SRE_EL3", "Interrupt Controller System Register Enable register (EL3)" ),
        ( 0b011, 0b100, "c12", "c8", 0b000 )  : ( "ICH_AP0R0_EL2", "Interrupt Controller Hyp Active Priorities Group 0 Register 0" ),
        ( 0b011, 0b100, "c12", "c8", 0b001 )  : ( "ICH_AP0R1_EL2", "Interrupt Controller Hyp Active Priorities Group 0 Register 1" ),
        ( 0b011, 0b100, "c12", "c8", 0b010 )  : ( "ICH_AP0R2_EL2", "Interrupt Controller Hyp Active Priorities Group 0 Register 2" ),
        ( 0b011, 0b100, "c12", "c8", 0b011 )  : ( "ICH_AP0R3_EL2", "Interrupt Controller Hyp Active Priorities Group 0 Register 3" ),
        ( 0b011, 0b100, "c12", "c9", 0b000 )  : ( "ICH_AP1R0_EL2", "Interrupt Controller Hyp Active Priorities Group 1 Register 0" ),
        ( 0b011, 0b100, "c12", "c9", 0b001 )  : ( "ICH_AP1R1_EL2", "Interrupt Controller Hyp Active Priorities Group 1 Register 1" ),
        ( 0b011, 0b100, "c12", "c9", 0b010 )  : ( "ICH_AP1R2_EL2", "Interrupt Controller Hyp Active Priorities Group 1 Register 2" ),
        ( 0b011, 0b100, "c12", "c9", 0b011 )  : ( "ICH_AP1R3_EL2", "Interrupt Controller Hyp Active Priorities Group 1 Register 3" ),
        ( 0b011, 0b100, "c12", "c11", 0b011 ) : ( "ICH_EISR_EL2", "Interrupt Controller End of Interrupt Status Register" ),
        ( 0b011, 0b100, "c12", "c11", 0b101 ) : ( "ICH_ELSR_EL2", "Interrupt Controller Empty List Register Status Register" ), # Named ICH_ELRSR_EL2 in 8.2 specifications.
        ( 0b011, 0b100, "c12", "c11", 0b000 ) : ( "ICH_HCR_EL2", "Interrupt Controller Hyp Control Register" ),
        ( 0b011, 0b100, "c12", "c12", 0b000 ) : ( "ICH_LR0_EL2", "Interrupt Controller List Register 0" ),
        ( 0b011, 0b100, "c12", "c12", 0b001 ) : ( "ICH_LR1_EL2", "Interrupt Controller List Register 1" ),
        ( 0b011, 0b100, "c12", "c12", 0b010 ) : ( "ICH_LR2_EL2", "Interrupt Controller List Register 2" ),
        ( 0b011, 0b100, "c12", "c12", 0b011 ) : ( "ICH_LR3_EL2", "Interrupt Controller List Register 3" ),
        ( 0b011, 0b100, "c12", "c12", 0b100 ) : ( "ICH_LR4_EL2", "Interrupt Controller List Register 4" ),
        ( 0b011, 0b100, "c12", "c12", 0b101 ) : ( "ICH_LR5_EL2", "Interrupt Controller List Register 5" ),
        ( 0b011, 0b100, "c12", "c12", 0b110 ) : ( "ICH_LR6_EL2", "Interrupt Controller List Register 6" ),
        ( 0b011, 0b100, "c12", "c12", 0b111 ) : ( "ICH_LR7_EL2", "Interrupt Controller List Register 7" ),
        ( 0b011, 0b100, "c12", "c13", 0b000 ) : ( "ICH_LR8_EL2", "Interrupt Controller List Register 8" ),
        ( 0b011, 0b100, "c12", "c13", 0b001 ) : ( "ICH_LR9_EL2", "Interrupt Controller List Register 9" ),
        ( 0b011, 0b100, "c12", "c13", 0b010 ) : ( "ICH_LR10_EL2", "Interrupt Controller List Register 10" ),
        ( 0b011, 0b100, "c12", "c13", 0b011 ) : ( "ICH_LR11_EL2", "Interrupt Controller List Register 11" ),
        ( 0b011, 0b100, "c12", "c13", 0b100 ) : ( "ICH_LR12_EL2", "Interrupt Controller List Register 12" ),
        ( 0b011, 0b100, "c12", "c13", 0b101 ) : ( "ICH_LR13_EL2", "Interrupt Controller List Register 13" ),
        ( 0b011, 0b100, "c12", "c13", 0b110 ) : ( "ICH_LR14_EL2", "Interrupt Controller List Register 14" ),
        ( 0b011, 0b100, "c12", "c13", 0b111 ) : ( "ICH_LR15_EL2", "Interrupt Controller List Register 15" ),
        ( 0b011, 0b100, "c12", "c11", 0b010 ) : ( "ICH_MISR_EL2", "Interrupt Controller Maintenance Interrupt State Register" ),
        ( 0b011, 0b100, "c12", "c11", 0b111 ) : ( "ICH_VMCR_EL2", "Interrupt Controller Virtual Machine Control Register" ),
        ( 0b011, 0b100, "c12", "c9", 0b100 )  : ( "ICH_VSEIR_EL2", "Interrupt Controller Virtual System Error Interrupt Register" ), # Not defined in 8.2 specifications.
        ( 0b011, 0b100, "c12", "c11", 0b001 ) : ( "ICH_VTR_EL2", "Interrupt Controller VGIC Type Register" ),
        ( 0b011, 0b100, "c12", "c11", 0b101 ) : ( "ICH_ELRSR_EL2", "Interrupt Controller Empty List Register Status Register" ),
        ( 0b011, 0b000, "c12", "c8", 0b100 )  : ( "ICV_AP0R0_EL1", "Interrupt Controller Virtual Active Priorities Group 0 Registers" ),
        ( 0b011, 0b000, "c12", "c8", 0b101 )  : ( "ICV_AP0R1_EL1", "Interrupt Controller Virtual Active Priorities Group 0 Registers" ),
        ( 0b011, 0b000, "c12", "c8", 0b110 )  : ( "ICV_AP0R2_EL1", "Interrupt Controller Virtual Active Priorities Group 0 Registers" ),
        ( 0b011, 0b000, "c12", "c8", 0b111 )  : ( "ICV_AP0R3_EL1", "Interrupt Controller Virtual Active Priorities Group 0 Registers" ),
        ( 0b011, 0b000, "c12", "c9", 0b000 )  : ( "ICV_AP1R0_EL1", "Interrupt Controller Virtual Active Priorities Group 1 Registers" ),
        ( 0b011, 0b000, "c12", "c9", 0b001 )  : ( "ICV_AP1R1_EL1", "Interrupt Controller Virtual Active Priorities Group 1 Registers" ),
        ( 0b011, 0b000, "c12", "c9", 0b010 )  : ( "ICV_AP1R2_EL1", "Interrupt Controller Virtual Active Priorities Group 1 Registers" ),
        ( 0b011, 0b000, "c12", "c9", 0b011 )  : ( "ICV_AP1R3_EL1", "Interrupt Controller Virtual Active Priorities Group 1 Registers" ),
        ( 0b011, 0b000, "c12", "c8", 0b011 )  : ( "ICV_BPR0_EL1", "Interrupt Controller Virtual Binary Point Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b011 ) : ( "ICV_BPR1_EL1", "Interrupt Controller Virtual Binary Point Register 1" ),
        ( 0b011, 0b000, "c12", "c12", 0b100 ) : ( "ICV_CTLR_EL1", "Interrupt Controller Virtual Control Register" ),
        ( 0b011, 0b000, "c12", "c8", 0b010 )  : ( "ICV_HPPIR0_EL1", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b010 ) : ( "ICV_HPPIR1_EL1", "Interrupt Controller Virtual Highest Priority Pending Interrupt Register 1" ),
        ( 0b011, 0b000, "c12", "c8", 0b000 )  : ( "ICV_IAR0_EL1", "Interrupt Controller Virtual Interrupt Acknowledge Register 0" ),
        ( 0b011, 0b000, "c12", "c12", 0b000 ) : ( "ICV_IAR1_EL1", "Interrupt Controller Virtual Interrupt Acknowledge Register 1" ),
        ( 0b011, 0b000, "c12", "c12", 0b110 ) : ( "ICV_IGRPEN0_EL1", "Interrupt Controller Virtual Interrupt Group 0 Enable register" ),
        ( 0b011, 0b000, "c12", "c12", 0b111 ) : ( "ICV_IGRPEN1_EL1", "Interrupt Controller Virtual Interrupt Group 1 Enable register" ),
        ( 0b011, 0b000, "c4", "c6", 0b000 )   : ( "ICV_PMR_EL1", "Interrupt Controller Virtual Interrupt Priority Mask Register" ),
        ( 0b011, 0b000, "c12", "c11", 0b011 ) : ( "ICV_RPR_EL1", "Interrupt Controller Virtual Running Priority Register" ),
}

# Aarch64 system co-processor registers.
AARCH64_SYSTEM_COPROC_REGISTERS = {
        ( 4, "c7", "c8", 6 )     : ( "AT S12E0R", "Address Translate Stages 1 and 2 EL0 Read" ),
        ( 4, "c7", "c8", 7 )     : ( "AT S12E0W", "Address Translate Stages 1 and 2 EL0 Write" ),
        ( 4, "c7", "c8", 4 )     : ( "AT S12E1R", "Address Translate Stages 1 and 2 EL1 Read" ),
        ( 4, "c7", "c8", 5 )     : ( "AT S12E1W", "Address Translate Stages 1 and 2 EL1 Write" ),
        ( 0, "c7", "c8", 2 )     : ( "AT S1E0R", "Address Translate Stage 1 EL0 Read" ),
        ( 0, "c7", "c8", 3 )     : ( "AT S1E0W", "Address Translate Stage 1 EL0 Write" ),
        ( 0, "c7", "c8", 0 )     : ( "AT S1E1R", "Address Translate Stage 1 EL1 Read" ),
        ( 0, "c7", "c9", 0 )     : ( "AT S1E1RP", "Address Translate Stage 1 EL1 Read PAN" ),
        ( 0, "c7", "c8", 1 )     : ( "AT S1E1W", "Address Translate Stage 1 EL1 Write" ),
        ( 0, "c7", "c9", 1 )     : ( "AT S1E1WP", "Address Translate Stage 1 EL1 Write PAN" ),
        ( 4, "c7", "c8", 0 )     : ( "AT S1E2R", "Address Translate Stage 1 EL2 Read" ),
        ( 4, "c7", "c8", 1 )     : ( "AT S1E2W", "Address Translate Stage 1 EL2 Write" ),
        ( 6, "c7", "c8", 0 )     : ( "AT S1E3R", "Address Translate Stage 1 EL3 Read" ),
        ( 6, "c7", "c8", 1 )     : ( "AT S1E3W", "Address Translate Stage 1 EL3 Write" ),
        ( 3, "c7", "c3", 4 )     : ( "CFP RCTX", "Control Flow Prediction Restriction by Context" ),
        ( 3, "c7", "c3", 7 )     : ( "CPP RCTX", "Cache Prefetch Prediction Restriction by Context" ),
        ( 0, "c7", "c10", 6 )    : ( "DC CGDSW", "Clean of Data and Allocation Tags by Set/Way" ),
        ( 3, "c7", "c10", 5 )    : ( "DC CGDVAC", "Clean of Data and Allocation Tags by VA to PoC" ),
        ( 3, "c7", "c13", 5 )    : ( "DC CGDVADP", "Clean of Data and Allocation Tags by VA to PoDP" ),
        ( 3, "c7", "c12", 5 )    : ( "DC CGDVAP", "Clean of Data and Allocation Tags by VA to PoP" ),
        ( 0, "c7", "c10", 4 )    : ( "DC CGSW", "Clean of Allocation Tags by Set/Way" ),
        ( 3, "c7", "c10", 3 )    : ( "DC CGVAC", "Clean of Allocation Tags by VA to PoC" ),
        ( 3, "c7", "c13", 3 )    : ( "DC CGVADP", "Clean of Allocation Tags by VA to PoDP" ),
        ( 3, "c7", "c12", 3 )    : ( "DC CGVAP", "Clean of Allocation Tags by VA to PoP" ),
        ( 0, "c7", "c14", 6 )    : ( "DC CIGDSW", "Clean and Invalidate of Data and Allocation Tags by Set/Way" ),
        ( 3, "c7", "c14", 5 )    : ( "DC CIGDVAC", "Clean and Invalidate of Data and Allocation Tags by VA to PoC" ),
        ( 0, "c7", "c14", 4 )    : ( "DC CIGSW", "Clean and Invalidate of Allocation Tags by Set/Way" ),
        ( 3, "c7", "c14", 3 )    : ( "DC CIGVAC", "Clean and Invalidate of Allocation Tags by VA to PoC" ),
        ( 0, "c7", "c14", 2 )    : ( "DC CISW", "Data or unified Cache line Clean and Invalidate by Set/Way" ),
        ( 3, "c7", "c14", 1 )    : ( "DC CIVAC", "Data or unified Cache line Clean and Invalidate by VA to PoC" ),
        ( 0, "c7", "c10", 2 )    : ( "DC CSW", "Data or unified Cache line Clean by Set/Way" ),
        ( 3, "c7", "c10", 1 )    : ( "DC CVAC", "Data or unified Cache line Clean by VA to PoC" ),
        ( 3, "c7", "c13", 1 )    : ( "DC CVADP", "Data or unified Cache line Clean by VA to PoDP" ),
        ( 3, "c7", "c12", 1 )    : ( "DC CVAP", "Data or unified Cache line Clean by VA to PoP" ),
        ( 3, "c7", "c11", 1 )    : ( "DC CVAU", "Data or unified Cache line Clean by VA to PoU" ),
        ( 3, "c7", "c4", 3 )     : ( "DC GVA", "Data Cache set Allocation Tag by VA" ),
        ( 3, "c7", "c4", 4 )     : ( "DC GZVA", "Data Cache set Allocation Tags and Zero by VA" ),
        ( 0, "c7", "c6", 6 )     : ( "DC IGDSW", "Invalidate of Data and Allocation Tags by Set/Way" ),
        ( 0, "c7", "c6", 5 )     : ( "DC IGDVAC", "Invalidate of Data and Allocation Tags by VA to PoC" ),
        ( 0, "c7", "c6", 4 )     : ( "DC IGSW", "Invalidate of Allocation Tags by Set/Way" ),
        ( 0, "c7", "c6", 3 )     : ( "DC IGVAC", "Invalidate of Allocation Tags by VA to PoC" ),
        ( 0, "c7", "c6", 2 )     : ( "DC ISW", "Data or unified Cache line Invalidate by Set/Way" ),
        ( 0, "c7", "c6", 1 )     : ( "DC IVAC", "Data or unified Cache line Invalidate by VA to PoC" ),
        ( 3, "c7", "c4", 1 )     : ( "DC ZVA", "Data Cache Zero by VA" ),
        ( 3, "c7", "c3", 5 )     : ( "DVP RCTX", "Data Value Prediction Restriction by Context" ),
        ( 0, "c7", "c5", 0 )     : ( "IC IALLU", "Instruction Cache Invalidate All to PoU" ),
        ( 0, "c7", "c1", 0 )     : ( "IC IALLUIS", "Instruction Cache Invalidate All to PoU, Inner Shareable" ),
        ( 3, "c7", "c5", 1 )     : ( "IC IVAU", "Instruction Cache line Invalidate by VA to PoU" ),
        ( 4, "c8", "c7", 4 )     : ( "TLBI ALLE1, TLBI ALLE1NXS", "TLB Invalidate All, EL1" ),
        ( 4, "c8", "c3", 4 )     : ( "TLBI ALLE1IS, TLBI ALLE1ISNXS", "TLB Invalidate All, EL1, Inner Shareable" ),
        ( 4, "c8", "c1", 4 )     : ( "TLBI ALLE1OS, TLBI ALLE1OSNXS", "TLB Invalidate All, EL1, Outer Shareable" ),
        ( 4, "c8", "c7", 0 )     : ( "TLBI ALLE2, TLBI ALLE2NXS", "TLB Invalidate All, EL2" ),
        ( 4, "c8", "c3", 0 )     : ( "TLBI ALLE2IS, TLBI ALLE2ISNXS", "TLB Invalidate All, EL2, Inner Shareable" ),
        ( 4, "c8", "c1", 0 )     : ( "TLBI ALLE2OS, TLBI ALLE2OSNXS", "TLB Invalidate All, EL2, Outer Shareable" ),
        ( 6, "c8", "c7", 0 )     : ( "TLBI ALLE3, TLBI ALLE3NXS", "TLB Invalidate All, EL3" ),
        ( 6, "c8", "c3", 0 )     : ( "TLBI ALLE3IS, TLBI ALLE3ISNXS", "TLB Invalidate All, EL3, Inner Shareable" ),
        ( 6, "c8", "c1", 0 )     : ( "TLBI ALLE3OS, TLBI ALLE3OSNXS", "TLB Invalidate All, EL3, Outer Shareable" ),
        ( 0, "c8", "c7", 2 )     : ( "TLBI ASIDE1, TLBI ASIDE1NXS", "TLB Invalidate by ASID, EL1" ),
        ( 0, "c8", "c3", 2 )     : ( "TLBI ASIDE1IS, TLBI ASIDE1ISNXS", "TLB Invalidate by ASID, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 2 )     : ( "TLBI ASIDE1OS, TLBI ASIDE1OSNXS", "TLB Invalidate by ASID, EL1, Outer Shareable" ),
        ( 4, "c8", "c4", 1 )     : ( "TLBI IPAS2E1, TLBI IPAS2E1NXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, EL1" ),
        ( 4, "c8", "c0", 1 )     : ( "TLBI IPAS2E1IS, TLBI IPAS2E1ISNXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, EL1, Inner Shareable" ),
        ( 4, "c8", "c4", 0 )     : ( "TLBI IPAS2E1OS, TLBI IPAS2E1OSNXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, EL1, Outer Shareable" ),
        ( 4, "c8", "c4", 5 )     : ( "TLBI IPAS2LE1, TLBI IPAS2LE1NXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1" ),
        ( 4, "c8", "c0", 5 )     : ( "TLBI IPAS2LE1IS, TLBI IPAS2LE1ISNXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1, Inner Shareable" ),
        ( 4, "c8", "c4", 4 )     : ( "TLBI IPAS2LE1OS, TLBI IPAS2LE1OSNXS", "TLB Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1, Outer Shareable" ),
        ( 4, "c8", "c4", 2 )     : ( "TLBI RIPAS2E1, TLBI RIPAS2E1NXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, EL1" ),
        ( 4, "c8", "c0", 2 )     : ( "TLBI RIPAS2E1IS, TLBI RIPAS2E1ISNXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, EL1, Inner Shareable" ),
        ( 4, "c8", "c4", 3 )     : ( "TLBI RIPAS2E1OS, TLBI RIPAS2E1OSNXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, EL1, Outer Shareable" ),
        ( 4, "c8", "c4", 6 )     : ( "TLBI RIPAS2LE1, TLBI RIPAS2LE1NXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1" ),
        ( 4, "c8", "c0", 6 )     : ( "TLBI RIPAS2LE1IS, TLBI RIPAS2LE1ISNXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1, Inner Shareable" ),
        ( 4, "c8", "c4", 7 )     : ( "TLBI RIPAS2LE1OS, TLBI RIPAS2LE1OSNXS", "TLB Range Invalidate by Intermediate Physical Address, Stage 2, Last level, EL1, Outer Shareable" ),
        ( 0, "c8", "c6", 3 )     : ( "TLBI RVAAE1, TLBI RVAAE1NXS", "TLB Range Invalidate by VA, All ASID, EL1" ),
        ( 0, "c8", "c2", 3 )     : ( "TLBI RVAAE1IS, TLBI RVAAE1ISNXS", "TLB Range Invalidate by VA, All ASID, EL1, Inner Shareable" ),
        ( 0, "c8", "c5", 3 )     : ( "TLBI RVAAE1OS, TLBI RVAAE1OSNXS", "TLB Range Invalidate by VA, All ASID, EL1, Outer Shareable" ),
        ( 0, "c8", "c6", 7 )     : ( "TLBI RVAALE1, TLBI RVAALE1NXS", "TLB Range Invalidate by VA, All ASID, Last level, EL1" ),
        ( 0, "c8", "c2", 7 )     : ( "TLBI RVAALE1IS, TLBI RVAALE1ISNXS", "TLB Range Invalidate by VA, All ASID, Last Level, EL1, Inner Shareable" ),
        ( 0, "c8", "c5", 7 )     : ( "TLBI RVAALE1OS, TLBI RVAALE1OSNXS", "TLB Range Invalidate by VA, All ASID, Last Level, EL1, Outer Shareable" ),
        ( 0, "c8", "c6", 1 )     : ( "TLBI RVAE1, TLBI RVAE1NXS", "TLB Range Invalidate by VA, EL1" ),
        ( 0, "c8", "c2", 1 )     : ( "TLBI RVAE1IS, TLBI RVAE1ISNXS", "TLB Range Invalidate by VA, EL1, Inner Shareable" ),
        ( 0, "c8", "c5", 1 )     : ( "TLBI RVAE1OS, TLBI RVAE1OSNXS", "TLB Range Invalidate by VA, EL1, Outer Shareable" ),
        ( 4, "c8", "c6", 1 )     : ( "TLBI RVAE2, TLBI RVAE2NXS", "TLB Range Invalidate by VA, EL2" ),
        ( 4, "c8", "c2", 1 )     : ( "TLBI RVAE2IS, TLBI RVAE2ISNXS", "TLB Range Invalidate by VA, EL2, Inner Shareable" ),
        ( 4, "c8", "c5", 1 )     : ( "TLBI RVAE2OS, TLBI RVAE2OSNXS", "TLB Range Invalidate by VA, EL2, Outer Shareable" ),
        ( 6, "c8", "c6", 1 )     : ( "TLBI RVAE3, TLBI RVAE3NXS", "TLB Range Invalidate by VA, EL3" ),
        ( 6, "c8", "c2", 1 )     : ( "TLBI RVAE3IS, TLBI RVAE3ISNXS", "TLB Range Invalidate by VA, EL3, Inner Shareable" ),
        ( 6, "c8", "c5", 1 )     : ( "TLBI RVAE3OS, TLBI RVAE3OSNXS", "TLB Range Invalidate by VA, EL3, Outer Shareable" ),
        ( 0, "c8", "c6", 5 )     : ( "TLBI RVALE1, TLBI RVALE1NXS", "TLB Range Invalidate by VA, Last level, EL1" ),
        ( 0, "c8", "c2", 5 )     : ( "TLBI RVALE1IS, TLBI RVALE1ISNXS", "TLB Range Invalidate by VA, Last level, EL1, Inner Shareable" ),
        ( 0, "c8", "c5", 5 )     : ( "TLBI RVALE1OS, TLBI RVALE1OSNXS", "TLB Range Invalidate by VA, Last level, EL1, Outer Shareable" ),
        ( 4, "c8", "c6", 5 )     : ( "TLBI RVALE2, TLBI RVALE2NXS", "TLB Range Invalidate by VA, Last level, EL2" ),
        ( 4, "c8", "c2", 5 )     : ( "TLBI RVALE2IS, TLBI RVALE2ISNXS", "TLB Range Invalidate by VA, Last level, EL2, Inner Shareable" ),
        ( 4, "c8", "c5", 5 )     : ( "TLBI RVALE2OS, TLBI RVALE2OSNXS", "TLB Range Invalidate by VA, Last level, EL2, Outer Shareable" ),
        ( 6, "c8", "c6", 5 )     : ( "TLBI RVALE3, TLBI RVALE3NXS", "TLB Range Invalidate by VA, Last level, EL3" ),
        ( 6, "c8", "c2", 5 )     : ( "TLBI RVALE3IS, TLBI RVALE3ISNXS", "TLB Range Invalidate by VA, Last level, EL3, Inner Shareable" ),
        ( 6, "c8", "c5", 5 )     : ( "TLBI RVALE3OS, TLBI RVALE3OSNXS", "TLB Range Invalidate by VA, Last level, EL3, Outer Shareable" ),
        ( 0, "c8", "c7", 3 )     : ( "TLBI VAAE1, TLBI VAAE1NXS", "TLB Invalidate by VA, All ASID, EL1" ),
        ( 0, "c8", "c3", 3 )     : ( "TLBI VAAE1IS, TLBI VAAE1ISNXS", "TLB Invalidate by VA, All ASID, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 3 )     : ( "TLBI VAAE1OS, TLBI VAAE1OSNXS", "TLB Invalidate by VA, All ASID, EL1, Outer Shareable" ),
        ( 0, "c8", "c7", 7 )     : ( "TLBI VAALE1, TLBI VAALE1NXS", "TLB Invalidate by VA, All ASID, Last level, EL1" ),
        ( 0, "c8", "c3", 7 )     : ( "TLBI VAALE1IS, TLBI VAALE1ISNXS", "TLB Invalidate by VA, All ASID, Last Level, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 7 )     : ( "TLBI VAALE1OS, TLBI VAALE1OSNXS", "TLB Invalidate by VA, All ASID, Last Level, EL1, Outer Shareable" ),
        ( 0, "c8", "c7", 1 )     : ( "TLBI VAE1, TLBI VAE1NXS", "TLB Invalidate by VA, EL1" ),
        ( 0, "c8", "c3", 1 )     : ( "TLBI VAE1IS, TLBI VAE1ISNXS", "TLB Invalidate by VA, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 1 )     : ( "TLBI VAE1OS, TLBI VAE1OSNXS", "TLB Invalidate by VA, EL1, Outer Shareable" ),
        ( 4, "c8", "c7", 1 )     : ( "TLBI VAE2, TLBI VAE2NXS", "TLB Invalidate by VA, EL2" ),
        ( 4, "c8", "c3", 1 )     : ( "TLBI VAE2IS, TLBI VAE2ISNXS", "TLB Invalidate by VA, EL2, Inner Shareable" ),
        ( 4, "c8", "c1", 1 )     : ( "TLBI VAE2OS, TLBI VAE2OSNXS", "TLB Invalidate by VA, EL2, Outer Shareable" ),
        ( 6, "c8", "c7", 1 )     : ( "TLBI VAE3, TLBI VAE3NXS", "TLB Invalidate by VA, EL3" ),
        ( 6, "c8", "c3", 1 )     : ( "TLBI VAE3IS, TLBI VAE3ISNXS", "TLB Invalidate by VA, EL3, Inner Shareable" ),
        ( 6, "c8", "c1", 1 )     : ( "TLBI VAE3OS, TLBI VAE3OSNXS", "TLB Invalidate by VA, EL3, Outer Shareable" ),
        ( 0, "c8", "c7", 5 )     : ( "TLBI VALE1, TLBI VALE1NXS", "TLB Invalidate by VA, Last level, EL1" ),
        ( 0, "c8", "c3", 5 )     : ( "TLBI VALE1IS, TLBI VALE1ISNXS", "TLB Invalidate by VA, Last level, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 5 )     : ( "TLBI VALE1OS, TLBI VALE1OSNXS", "TLB Invalidate by VA, Last level, EL1, Outer Shareable" ),
        ( 4, "c8", "c7", 5 )     : ( "TLBI VALE2, TLBI VALE2NXS", "TLB Invalidate by VA, Last level, EL2" ),
        ( 4, "c8", "c3", 5 )     : ( "TLBI VALE2IS, TLBI VALE2ISNXS", "TLB Invalidate by VA, Last level, EL2, Inner Shareable" ),
        ( 4, "c8", "c1", 5 )     : ( "TLBI VALE2OS, TLBI VALE2OSNXS", "TLB Invalidate by VA, Last level, EL2, Outer Shareable" ),
        ( 6, "c8", "c7", 5 )     : ( "TLBI VALE3, TLBI VALE3NXS", "TLB Invalidate by VA, Last level, EL3" ),
        ( 6, "c8", "c3", 5 )     : ( "TLBI VALE3IS, TLBI VALE3ISNXS", "TLB Invalidate by VA, Last level, EL3, Inner Shareable" ),
        ( 6, "c8", "c1", 5 )     : ( "TLBI VALE3OS, TLBI VALE3OSNXS", "TLB Invalidate by VA, Last level, EL3, Outer Shareable" ),
        ( 0, "c8", "c7", 0 )     : ( "TLBI VMALLE1, TLBI VMALLE1NXS", "TLB Invalidate by VMID, All at stage 1, EL1" ),
        ( 0, "c8", "c3", 0 )     : ( "TLBI VMALLE1IS, TLBI VMALLE1ISNXS", "TLB Invalidate by VMID, All at stage 1, EL1, Inner Shareable" ),
        ( 0, "c8", "c1", 0 )     : ( "TLBI VMALLE1OS, TLBI VMALLE1OSNXS", "TLB Invalidate by VMID, All at stage 1, EL1, Outer Shareable" ),
        ( 4, "c8", "c7", 6 )     : ( "TLBI VMALLS12E1, TLBI VMALLS12E1NXS", "TLB Invalidate by VMID, All at Stage 1 and 2, EL1" ),
        ( 4, "c8", "c3", 6 )     : ( "TLBI VMALLS12E1IS, TLBI VMALLS12E1ISNXS", "TLB Invalidate by VMID, All at Stage 1 and 2, EL1, Inner Shareable" ),
        ( 4, "c8", "c1", 6 )     : ( "TLBI VMALLS12E1OS, TLBI VMALLS12E1OSNXS", "TLB Invalidate by VMID, All at Stage 1 and 2, EL1, Outer Shareable" ),
}

# Aarch32 fields.
AARCH32_COPROC_FIELDS = {
        "DACR" : {
            (0, 2) : ("D0", "Domain 0"),
            (2, 2) : ("D1", "Domain 1"),
            (4, 2) : ("D2", "Domain 2"),
            (6, 2) : ("D3", "Domain 3"),
            (8, 2) : ("D4", "Domain 4"),
            (10, 2) : ("D5", "Domain 5"),
            (12, 2) : ("D6", "Domain 6"),
            (14, 2) : ("D7", "Domain 7"),
            (16, 2) : ("D8", "Domain 8"),
            (18, 2) : ("D9", "Domain 9"),
            (20, 2) : ("D10", "Domain 10"),
            (22, 2) : ("D11", "Domain 11"),
            (24, 2) : ("D12", "Domain 12"),
            (26, 2) : ("D13", "Domain 13"),
            (28, 2) : ("D14", "Domain 14"),
            (30, 2) : ("D15", "Domain 15"),
        },
        "MIDR" : {
            (0, 3)  : ( "Revision", "Revision number" ),
            (4, 12) : ( "PartNum", "Primary Part Number" ),
            (16, 4) : ( "Architecture", "Architecture version" ),
            (20, 4) : ( "Variant", "Variant number" ),
            (24, 8) : ( "Implementer", "Implementer code" )
        },
        "ID_ISAR0" : {
            (0, 4)  : ( "Swap", "Swap instructions" ),
            (4, 4)  : ( "BitCount", "Bit Counting instructions" ),
            (8, 4)  : ( "BitField", "BitField instructions" ),
            (12, 4) : ( "CmpBranch", "Compare and Branch instructions" ),
            (16, 4) : ( "Coproc", "System register access instructions" ),
            (20, 4) : ( "Debug", "Debug instructions" ),
            (24, 4) : ( "Divide", "Divide instructions" )
        },
        "ID_ISAR1" : {
            (0, 4)  : ( "Endian", "SETEND instruction" ),
            (4, 4)  : ( "Except", "Exception-handling instructions" ),
            (8, 4)  : ( "Except_AR", "A and R-profile exception handling instructions" ),
            (12, 4) : ( "Extend", "Extend instructions" ),
            (16, 4) : ( "IfThen", "If-Then instructions" ),
            (20, 4) : ( "Immediate", "Long immediate instructions" ),
            (24, 4) : ( "Interwork", "Interworking instructions" ),
            (28, 4) : ( "Jazelle", "Jazelle extension instructions" )
        },
        "ID_ISAR2" : {
            (0, 4)  : ( "LoadStore", "Additional load/store instructions" ),
            (4, 4)  : ( "MemHint", "Memory Hint instructions" ),
            (8, 4)  : ( "MultiAccessInt", "Interruptible multi-access instructions" ),
            (12, 4) : ( "Mult", "Multiply instructions" ),
            (16, 4) : ( "MultS", "Advanced signed Multiply instructions" ),
            (20, 4) : ( "MultU", "Advanced unsigned Multiply instructions" ),
            (24, 4) : ( "PSR_AR", "A and R-profile instructions to manipulate the PSR" ),
            (28, 4) : ( "Reversal", "Reversal instructions" )
        },
        "ID_ISAR3" : {
            (0, 4)  : ( "Saturate", "Saturate instructions" ),
            (4, 4)  : ( "SIMD", "SIMD instructions" ),
            (8, 4)  : ( "SVC", "SVC instructions" ),
            (12, 4) : ( "SyncPrim", "Synchronization Primitive instructions" ),
            (16, 4) : ( "TabBranch", "Table Branch instructions" ),
            (20, 4) : ( "T32Copy", "T32 non-flag setting MOV instructions" ),
            (24, 4) : ( "TrueNOP", "true NOP instructions" ),
            (28, 4) : ( "T32EE", "T32EE instructions" )
        },
        "ID_ISAR4" : {
            (0, 4)  : ( "Unpriv", "Unprivileged instructions" ),
            (4, 4)  : ( "WithShifts", "Instructions with shifts" ),
            (8, 4)  : ( "Writeback", "Writeback addressing mode" ),
            (12, 4) : ( "SMC", "SMC instructions" ),
            (16, 4) : ( "Barrier", "Barrier instructions" ),
            (20, 4) : ( "SyncPrim_frac", "Synchronization Primitive instructions" ),
            (24, 4) : ( "PSR_M", "M-profile instructions to modify the PSR" ),
            (28, 4) : ( "SWP_frac", "Bus locking for SWP and SWPB instructions" )
        },
        "ID_ISAR5" : {
            (0, 4)  : ( "SEVL", "SEVL instructions" ),
            (4, 4)  : ( "AES", "AES instructions" ),
            (8, 4)  : ( "SHA1", "SHA1 instructions" ),
            (12, 4) : ( "SHA2", "SHA2 instructions" ),
            (16, 4) : ( "CRC32", "CRC32 instructions" ),
            (24, 4) : ( "RDM", "VQRDMLAH and VQRDMLSH instructions" ),
            (28, 4) : ( "VCMA", "VCMLA and VCADD instructions" )
        },
        "ID_ISAR6" : {
            (0, 4)  : ( "JSCVT", "JavaScript conversion instruction" ),
            (4, 4)  : ( "DP", "Dot product instructions" ),
            (8, 4)  : ( "FHM", "VFMAL and VFMSL instructions" ),
            (12, 4) : ( "SB", "SB instruction" ),
            (16, 4) : ( "SPECRES", "Speculation invalidation instructions" ),
            (20, 4) : ( "BF16", "BFloat16 instructions" ),
            (24, 4) : ( "I8MM", "Int8 matrix multiplication instructions" ),
        },
        "FPSCR" : {
            0 : ( "IOC", "Invalid Operation exception" ),
            1 : ( "DZC", "Division by Zero exception" ),
            2 : ( "OFC", "Overflow exception" ),
            3 : ( "UFC", "Underflow exception" ),
            4 : ( "IXC", "Inexact exception" ),
            7 : ( "IDC", "Input Denormal exception" ),
            8 : ( "IOE", "Invalid Operation floating-point exception" ),
            9 : ( "DZE", "Divide by Zero floating-point exception" ),
            10 : ( "OFE", "Overflow floating-point exception" ),
            11 : ( "UFE", "Underflow floating-point exception" ),
            12 : ( "IXE", "Inexact floating-point exception" ),
            15 : ( "IDE", "Input Denormal floating-point exception" ),
            19 : ( "FZ16", "Flush-to-zero mode on half-precision instructions" ),
            (20, 2) : ( "Stride", "Stride" ),
            (22, 2) : ( "RMode", "Rounding Mode control field" ),
            24 : ( "FZ", "Flush-to-zero mode" ),
            25 : ( "DN", "Default NaN mode" ),
            26 : ( "AHP", "Alternative Half-Precision" ),
            27 : ( "QC", "Saturation" ),
            28 : ( "V", "Overflow flag" ),
            29 : ( "C", "Carry flag" ),
            30 : ( "Z", "Zero flag" ),
            31 : ( "N", "Negative flag" )
        },
        "HCR" : {
            0 : ( "VM", "Virtualization MMU enable" ),
            1 : ( "SWIO", "Set/Way Invalidation Override" ),
            2 : ( "PTW", "Protected Table Walk" ),
            3 : ( "FMO", "FIQ Mask Override" ),
            4 : ( "IMO", "IRQ Mask Override" ),
            5 : ( "AMO", "Asynchronous Abort Mask Override" ),
            6 : ( "VE", "Virtual FIQ exception" ),
            7 : ( "VI", "Virtual IRQ exception" ),
            8 : ( "VA", "Virtual Asynchronous Abort exception" ),
            9 : ( "FB", "Force Broadcast" ),
            10 : ( "BSU_0", "Barrier Shareability Upgrade" ),
            11 : ( "BSU_1", "Barrier Shareability Upgrade" ),
            12 : ( "DC", "Default cacheable" ),
            13 : ( "TWI", "Trap WFI" ),
            14 : ( "TWE", "Trap WFE" ),
            15 : ( "TID0", "Trap ID Group 0" ),
            16 : ( "TID1", "Trap ID Group 1" ),
            17 : ( "TID2", "Trap ID Group 2" ),
            18 : ( "TID3", "Trap ID Group 3" ),
            19 : ( "TSC", "Trap SMC instruction" ),
            20 : ( "TIDCP", "Trap Implementation Dependent functionality" ),
            21 : ( "TAC", "Trap ACTLR accesses" ),
            22 : ( "TSW", "Trap Data/Unified Cache maintenance operations by Set/Way" ),
            23 : ( "TPC", "Trap Data/Unified Cache maintenance operations to Point of Coherency" ),
            24 : ( "TPU", "Trap Cache maintenance instructions to Point of Unification" ),
            25 : ( "TTLB", "Trap TLB maintenance instructions" ),
            26 : ( "TVM", "Trap Virtual Memory controls" ),
            27 : ( "TGE", "Trap General Exceptions" ),
            29 : ( "HCD", "Hypervisor Call Disable" ),
            30 : ( "TRVM", "Trap Read of Virtual Memory controls" )
        },
        "HCR2" : {
            0 : ( "CD", "Stage 2 Data cache disable" ),
            1 : ( "ID", "Stage 2 Instruction cache disable" ),
            4 : ( "TERR", "Trap Error record accesses" ),
            5 : ( "TEA", "Route synchronous External Abort exceptions to EL2" ),
            6 : ( "MIOCNCE", "Mismatched Inner/Outer Cacheable Non-Coherency Enable" ),
            17 : ( "TID4", "Trap ID group 4" ),
            18 : ( "TICAB", "Trap ICIALLUIS cache maintenance instructions" ),
            20 : ( "TOCU", "Trap cache maintenance instructions that operate to the Point of Unification" ),
            22 : ( "TTLBIS", "Trap TLB maintenance instructions that operate on the Inner Shareable domain" )
        },
        "SCR" : {
            0 : ( "NS", "Non-secure" ),
            1 : ( "IRQ", "IRQ handler" ),
            2 : ( "FIQ", "FIQ handler" ),
            3 : ( "EA", "External Abort handler" ),
            4 : ( "FW", "Can mask Non-secure FIQ" ),
            5 : ( "AW", "Can mask Non-secure external aborts" ),
            6 : ( "nET", "Not Early Termination" ),
            7 : ( "SCD", "Secure Monitor Call disable" ),
            8 : ( "HCE", "Hypervisor Call instruction enable" ),
            9 : ( "SIF", "Secure instruction fetch" ),
            12 : ( "TWI", "Traps WFI instructions to Monitor mode" ),
            13 : ( "TWE", "Traps WFE instructions to Monitor mode" ),
            15 : ( "TERR", "Trap Error record accesses" )
        },
        "SCTLR" : {
            0 : ( "M", "MMU Enable" ),
            1 : ( "A", "Alignment" ),
            2 : ( "C", "Cache Enable" ),
            3 : ( "nTLSMD", "No Trap Load Multiple and Store Multiple to Device-nGRE/Device-nGnRE/Device-nGnRnE memory" ),
            4 : ( "LSMAOE", "Load Multiple and Store Multiple Atomicity and Ordering Enable" ),
            5 : ( "CP15BEN", "System instruction memory barrier enable" ),
            7 : ( "ITD", "IT Disable" ),
            8 : ( "SETEND", "SETEND instruction disable" ),
            10 : ( "SW", "SWP/SWPB Enable" ),
            11 : ( "Z", "Branch Prediction Enable" ),
            12 : ( "I", "Instruction cache Enable" ),
            13 : ( "V", "High exception vectors" ),
            14 : ( "RR", "Round-robin cache" ),
            16 : ( "nTWI", "Traps EL0 execution of WFI instructions to Undefined mode" ),
            17 : ( "HA", "Hardware Access Enable" ),
            18 : ( "nTWE", "Traps EL0 execution of WFE instructions to Undefined mode" ),
            19 : ( "WXN", "Write permission implies XN" ),
            20 : ( "UWXN", "Unprivileged write permission implies PL1 XN" ),
            21 : ( "FI", "Fast Interrupts configuration" ),
            23 : ( "SPAN", "Set Privileged Access Never" ),
            24 : ( "VE", "Interrupt Vectors Enable" ),
            25 : ( "EE", "Exception Endianness" ),
            27 : ( "NMFI", "Non-maskable Fast Interrupts" ),
            28 : ( "TRE", "TEX Remap Enable" ),
            29 : ( "AFE", "Access Flag Enable" ),
            30 : ( "TE", "Thumb Exception Enable" ),
            31 : ( "DSSBS", "Default PSTATE.SSBS value on Exception Entry" )
        },
        "HSCTLR" : {
            0 : ( "M", "MMU Enable" ),
            1 : ( "A", "Alignment" ),
            2 : ( "C", "Cache Enable" ),
            3 : ( "SA/nTLSMD", "Stack alignment check or No Trap Load Multiple and Store Multiple to Device-nGRE/Device-nGnRE/Device-nGnRnE memory" ),
            4 : ( "LSMAOE", "Load Multiple and Store Multiple Atomicity and Ordering Enable" ),
            5 : ( "CP15BEN", "System instruction memory barrier enable" ),
            7 : ( "ITD", "IT Disable" ),
            8 : ( "SED", "SETEND instruction disable" ),
            12 : ( "I", "Instruction cache Enable" ),
            19 : ( "WXN", "Write permission implies XN" ),
            25 : ( "EE", "Exception Endianness" ),
            30 : ( "TE", "Thumb Exception Enable" ),
            31 : ( "DSSBS", "Default PSTATE.SSBS value on Exception Entry" )
        },
        "NSACR" : {
            10 : ( "CP10", "CP10 access in the NS state" ),
            11 : ( "CP11", "CP11 access in the NS state" ),
            14 : ( "NSD32DIS", "Disable the NS use of D16-D31 of the VFP register file" ),
            15 : ( "NSASEDIS", "Disable NS Advanced SIMD Extension functionality" ),
            16 : ( "PLE", "NS access to the Preload Engine resources" ),
            17 : ( "TL", "Lockable TLB entries can be allocated in NS state" ),
            18 : ( "NS_SMP", "SMP bit of the Auxiliary Control Register is writable in NS state" ),
            20 : ( "NSTRCDIS", "Disables Non-secure System register accesses to all implemented trace registers" )
        },
}

# Aarch64 fields.
AARCH64_SYSREG_FIELDS = {
        "CurrentEL" : {
            (2, 2) : ( "EL", "Current Exception Level" )
        },
        "DAIF" : {
            6 : ( "F", "FIQ mask" ),
            7 : ( "I", "IRQ mask" ),
            8 : ( "A", "SError interrupt mask" ),
            9 : ( "D", "Process state D mask" )
        },
        "FPCR" : {
            0 : ( "FIZ", "Flush Inputs to Zero" ),
            1 : ( "AH", "Alternate Handling" ),
            2 : ( "NEP", "Controls how the output elements other than the lowest element of the vector are determined for Advanced SIMD scalar instructions" ),
            8 : ( "IOE", "Invalid Operation exception trap enable" ),
            9 : ( "DZE", "Division by Zero exception trap enable" ),
            10 : ( "OFE", "Overflow exception trap enable" ),
            11 : ( "UFE", "Underflow exception trap enable" ),
            12 : ( "IXE", "Inexact exception trap enable" ),
            15 : ( "IDE", "Input Denormal exception trap enable" ),
            19 : ( "FZ16", "Flush-to-zero mode on half-precision instructions" ),
            # 22-23 : RMode
            24 : ( "FZ", "Flush-to-zero-mode" ),
            25 : ( "DN", "Default NaN mode" ),
            26 : ( "AHP", "Alternative Half-Precision" )
        },
        "FPSR" : {
            0 : ( "IOC", "Invalid Operation exception" ),
            1 : ( "DZC", "Division by Zero exception" ),
            2 : ( "OFC", "Overflow exception" ),
            3 : ( "UFC", "Underflow exception" ),
            4 : ( "IXC", "Inexact exception" ),
            7 : ( "IDC", "Input Denormal exception" ),
            27 : ( "QC", "Saturation" ),
            28 : ( "V", "Overflow flag" ),
            29 : ( "C", "Carry flag" ),
            30 : ( "Z", "Zero flag" ),
            31 : ( "N", "Negative flag" )
        },
        "HCR_EL2" : {
            0 : ( "VM", "Virtualization MMU enable" ),
            1 : ( "SWIO", "Set/Way Invalidation Override" ),
            2 : ( "PTW", "Protected Table Walk" ),
            3 : ( "FMO", "FIQ Mask Override" ),
            4 : ( "IMO", "IRQ Mask Override" ),
            5 : ( "AMO", "Asynchronous Abort Mask Override" ),
            6 : ( "VF", "Virtual FIQ exception" ),
            7 : ( "VI", "Virtual IRQ exception" ),
            8 : ( "VA", "Virtual Asynchronous Abort exception" ),
            9 : ( "FB", "Force Broadcast" ),
            10 : ( "BSU_0", "Barrier Shareability Upgrade" ),
            11 : ( "BSU_1", "Barrier Shareability Upgrade" ),
            12 : ( "DC", "Default cacheable" ),
            13 : ( "TWI", "Trap WFI" ),
            14 : ( "TWE", "Trap WFE" ),
            15 : ( "TID0", "Trap ID Group 0" ),
            16 : ( "TID1", "Trap ID Group 1" ),
            17 : ( "TID2", "Trap ID Group 2" ),
            18 : ( "TID3", "Trap ID Group 3" ),
            19 : ( "TSC", "Trap SMC instruction" ),
            20 : ( "TIDCP", "Trap Implementation Dependent functionality" ),
            21 : ( "TACR", "Trap ACTLR accesses" ),
            22 : ( "TSW", "Trap Data/Unified Cache maintenance operations by Set/Way" ),
            23 : ( "TPCP", "Trap Data/Unified Cache maintenance operations to Point of Coherency" ),
            24 : ( "TPU", "Trap Cache maintenance instructions to Point of Unification" ),
            25 : ( "TTLB", "Trap TLB maintenance instructions" ),
            26 : ( "TVM", "Trap Virtual Memory controls" ),
            27 : ( "TGE", "Trap General Exceptions" ),
            28 : ( "TDZ", "Trap DC ZVA instructions" ),
            29 : ( "HCD", "Hypervisor Call Disable" ),
            30 : ( "TRVM", "Trap Read of Virtual Memory controls" ),
            31 : ( "RW", "Lower level is AArch64" ),
            32 : ( "CD", "Stage 2 Data cache disable" ),
            33 : ( "ID", "Stage 2 Instruction cache disable" ),
            34 : ( "E2H", "EL2 Host" ),
            35 : ( "TLOR", "Trap LOR registers" ),
            36 : ( "TERR", "Trap Error record accesses" ),
            37 : ( "TEA", "Route synchronous External Abort exceptions to EL2" ),
            38 : ( "MIOCNCE", "Mismatched Inner/Outer Cacheable Non-Coherency Enable" ),
            40 : ( "APK", "Trap registers holding \"key\" values for Pointer Authentication" ),
            41 : ( "API", "Trap instructions related to Pointer Authentication" ),
            42 : ( "NV", "Nested Virtualization" ),
            43 : ( "NV1", "Nested Virtualization" ),
            44 : ( "AT", "Address Translation" ),
            45 : ( "NV2", "Nested Virtualization" ),
            46 : ( "FWB", "Forced Write-Back" ),
            47 : ( "FIEN", "Fault Injection Enable" ),
            49 : ( "TID4", "Trap ID Group 4" ),
            50 : ( "TICAB", "Trap ICIALLUIS/IC IALLUIS cache maintenance instructions" ),
            51 : ( "AMVOFFEN", "Activity Monitors Virtual Offsets Enable"),
            52 : ( "TOCU", "Trap cache maintenance instructions that operate to the Point of Unification" ),
            53 : ( "EnSCXT", "Enable Access to the SCXTNUM_EL1 and SCXTNUM_EL0 registers" ),
            54 : ( "TTLBIS", "Trap TLB maintenance instructions that operate on the Inner Shareable domain" ),
            55 : ( "TTLBOS", "Trap TLB maintenance instructions that operate on the Outer Shareable domain" ),
            56 : ( "ATA", "Allocation Tag Access" ),
            57 : ( "DCT", "Default Cacheability Tagging" ),
            58 : ( "TID5", "Trap ID Group 5" ),
            59 : ( "TWEDEn", "TWE Delay Enable" ),
            (60, 4): ( "TWEDEL", "TWE Delay" )
        },
        "SCR_EL3" : {
            0 : ( "NS", "Non-secure" ),
            1 : ( "IRQ", "IRQ handler" ),
            2 : ( "FIQ", "FIQ handler" ),
            3 : ( "EA", "External Abort handler" ),
            7 : ( "SMD", "Secure Monitor Call disable" ),
            8 : ( "HCE", "Hypervisor Call instruction enable" ),
            9 : ( "SIF", "Secure instruction fetch" ),
            10 : ( "RW", "Lower level is AArch64" ),
            11 : ( "ST", "Traps Secure EL1 accesses to the Counter-timer Physical Secure timer registers to EL3, from AArch64 state only." ),
            12 : ( "TWI", "Traps WFI instructions to Monitor mode" ),
            13 : ( "TWE", "Traps WFE instructions to Monitor mode" ),
            14 : ( "TLOR", "Traps LOR registers" ),
            15 : ( "TERR", "Trap Error record accesses" ),
            16 : ( "APK", "Trap registers holding \"key\" values for Pointer Authentication" ),
            17 : ( "API", "Trap instructions related to Pointer Authentication" ),
            18 : ( "EEL2", "Secure EL2 Enable" ),
            19 : ( "EASE", "External aborts to SError interrupt vector" ),
            20 : ( "NMEA", "Non-maskable External Aborts" ),
            21 : ( "FIEN", "Fault Injection enable" ),
            25 : ( "EnSCXT", "Enable access to the SCXTNUM_EL2, SCXTNUM_EL1, and SCXTNUM_EL0 registers" ),
            26 : ( "ATA", "Allocation Tag Access" ),
            27 : ( "FGTEn", "Fine-Grained Traps Enable" ),
            28 : ( "ECVEn", "ECV Enable" ),
            29 : ( "TWEDEn", "TWE Delay Enable" ),
            (30, 4) : ( "TWEDEL", "TWE Delay" ),
            35 : ( "AMVOFFEN", "Activity Monitors Virtual Offsets Enable" ),
            36 : ( "EnAS0", "Trap execution of an ST64BV0 instruction at EL0, EL1, or EL2 to EL3" ),
            37 : ( "ADEn", "Enable access to the ACCDATA_EL1 register at EL1 and EL2" ),
            38 : ( "HXEn", "Enables access to the HCRX_EL2 register at EL2 from EL3" )
        },
        "SCTLR_EL1" : {
            0 : ( "M", "MMU Enable" ),
            1 : ( "A", "Alignment" ),
            2 : ( "C", "Cache Enable" ),
            3 : ( "SA", "Stack alignment check" ),
            4 : ( "SA0", "Stack alignment check for EL0" ),
            5 : ( "CP15BEN", "System instruction memory barrier enable" ),
            6 : ( "THEE/nAA", "T32EE enable or Non-aligned access" ),
            7 : ( "ITD", "IT Disable" ),
            8 : ( "SED", "SETEND instruction disable" ),
            9 : ( "UMA", "User Mask Access" ),
            10 : ( "EnRCTX", "Enable EL0 Access to CFP RCTX, DVP RCT and CPP RCTX instructions" ),
            11 : ( "EOS", "Exception Exit is Context Synchronizing" ),
            12 : ( "I", "Instruction cache Enable" ),
            13 : ( "EnDB", "Enable pointer authentication (using the APDBKey_EL1 key) of instruction addresses in the EL1&0 translation regime" ),
            14 : ( "DZE", "Access to DC ZVA instruction at EL0" ),
            15 : ( "UCT", "Access to CTR_EL0 to EL0" ),
            16 : ( "nTWI", "Traps EL0 execution of WFI instructions to Undefined mode" ),
            18 : ( "nTWE", "Traps EL0 execution of WFE instructions to Undefined mode" ),
            19 : ( "WXN", "Write permission implies XN" ),
            20 : ( "TSCXT", "Trap EL0 Access to the SCXTNUM_EL0 register, when EL0 is using AArch64" ),
            21 : ( "IESB", "Implicit Error Synchronization event enable" ),
            22 : ( "EIS", "Exception Entry is Context Synchronizing" ),
            23 : ( "SPAN", "Set Privileged Access Never, on taking an exception to EL1" ),
            24 : ( "E0E", "Endianess of explicit data accesses at EL0" ),
            25 : ( "EE", "Exception Endianness" ),
            26 : ( "UCI", "Enable EL0 access to DC CVAU, DC CIVAC, DC CVAC and DC IVAU instructions" ),
            27 : ( "EnDA", "Enable pointer authentication (using the APDAKey_EL1 key) of instruction addresses in the EL1&0 translation regime" ),
            28 : ( "nTLSMD", "No Trap Load Multiple and Store Multiple to Device-nGRE/Device-nGnRE/Device-nGnRnE memory" ),
            29 : ( "LSMAOE", "Load Multiple and Store Multiple Atomicity and Ordering Enable" ),
            30 : ( "EnIB", "Enable pointer authentication (using the APIBKey_EL1 key) of instruction addresses in the EL1&0 translation regime" ),
            31 : ( "EnIA", "Enable pointer authentication (using the APIAKey_EL1 key) of instruction addresses in the EL1&0 translation regime" ),
            35 : ( "BT0", "PAC Branch Type compatibility at EL0" ),
            36 : ( "BT1", "PAC Branch Type compatibility at EL1" ),
            37 : ( "ITFSB", "Tag Check Faults are synchronized on entry to EL1" ),
            (38, 2) : ( "TCF0", "Tag Check Fault in EL0" ),
            (40, 2) : ( "TCF", "Tag Check Fault in EL1" ),
            42 : ( "ATA0", "Allocation Tag Access in EL0" ),
            43 : ( "ATA1", "Allocation Tag Access in EL1" ),
            44 : ( "DSSBS", "Default PSTATE.SSBS value on Exception Entry" ),
            45 : ( "TWEDEn", "TWE Delay Enable" ),
            (46, 4) : ( "TWEDEL", "TWE Delay" ),
            54 : ( "EnASR", "When HCR_EL2.{E2H, TGE} != {1, 1}, traps execution of an ST64BV instruction at EL0 to EL1" ),
            55 : ( "EnAS0", "When HCR_EL2.{E2H, TGE} != {1, 1}, traps execution of an ST64BV0 instruction at EL0 to EL1" ),
            56 : ( "EnALS", "When HCR_EL2.{E2H, TGE} != {1, 1}, traps execution of an LD64B or ST64B instruction at EL0 to EL1" ),
            57 : ( "EPAN", "Enhanced Privileged Access Never" )
        },
        "SCTLR_EL2" : {
            0 : ( "M", "MMU Enable" ),
            1 : ( "A", "Alignment" ),
            2 : ( "C", "Cache Enable" ),
            3 : ( "SA", "SP alignment check" ),
            4 : ( "SA0", "SP Alignment check enable for EL0" ),
            5 : ( "CP15BEN", "System instruction memory barrier enable" ),
            6 : ( "nAA", "Non-aligned access" ),
            7 : ( "ITD", "IT Disable" ),
            8 : ( "SED", "SETEND instruction disable" ),
            10 : ( "EnRCTX", "Enable EL0 Access to CFP RCTX, DVP RCT and CPP RCTX instructions" ),
            11 : ( "EOS", "Exception exit is a context synchronization event" ),
            12 : ( "I", "Instruction cache Enable" ),
            13 : ( "EnDB", "Enable pointer authentication (using the APDBKey_EL1 key) of instruction addresses in the EL2 or EL2&0 translation regime" ),
            14 : ( "DZE", "Trap execution of DC ZVA instructions at EL0 to EL2" ),
            15 : ( "UCT", "Trap EL0 accesses to the CTR_EL0 to EL2" ),
            16 : ( "nTWI", "Trap execution of WFI instructions at EL0 to EL2" ),
            18 : ( "nTWE", "Trap execution of WFE instructions at EL0 to EL2" ),
            19 : ( "WXN", "Write permission implies XN" ),
            20 : ( "TSCXT", "Trap EL0 Access to the SCXTNUM_EL0 register" ),
            21 : ( "IESB", "Implicit Error Synchronization event enable" ),
            22 : ( "EIS", "Exception entry is a context synchronization event" ),
            23 : ( "SPAN", "Set Privileged Access Never, on taking an exception to EL2" ),
            24 : ( "E0E", "Endianness of data accesses at EL0" ),
            25 : ( "EE", "Exception Endianness" ),
            26 : ( "UCI", "Trap execution of cache maintenance instructions at EL0 to EL2" ),
            27 : ( "EnDA", "Enable pointer authentication (using the APDAKey_EL1 key) of instruction addresses in the EL2 or EL2&0 translation regime" ),
            28 : ( "nTLSMD", "No Trap Load Multiple and Store Multiple to Device-nGRE/Device-nGnRE/Device-nGnRnE memory" ),
            29 : ( "LSMAOE", "Load Multiple and Store Multiple Atomicity and Ordering Enable" ),
            30 : ( "EnIB", "Enable pointer authentication (using the APIBKey_EL1 key) of instruction addresses in the EL2 or EL2&0 translation regime" ),
            31 : ( "EnIA", "Enable pointer authentication (using the APIAKey_EL1 key) of instruction addresses in the EL2 or EL2&0 translation regime" ),
            35 : ( "BT0", "PAC Branch Type compatibility at EL0" ),
            36 : ( "BT", "PAC Branch Type compatibility at EL2" ),
            37 : ( "ITFSB", "Tag Check Faults are synchronized on entry to EL2" ),
            (38, 2) : ( "TCF0", "Tag Check Fault in EL0" ),
            (40, 2) : ( "TCF", "Tag Check Fault in EL2" ),
            42 : ( "ATA0", "Allocation Tag Access in EL0" ),
            43 : ( "ATA", "Allocation Tag Access in EL2" ),
            44 : ( "DSSBS", "Default PSTATE.SSBS value on Exception Entry" ),
            45 : ( "TWEDEn", "TWE Delay Enable" ),
            (46, 4) : ( "TWEDEL", "TWE Delay" ),
            54 : ( "EnASR", "Trap execution of an ST64BV instruction at EL0 to EL2" ),
            55 : ( "EnAS0", "Trap execution of an ST64BV0 instruction at EL0 to EL2" ),
            56 : ( "EnALS", "Trap execution of an LD64B or ST64B instruction at EL0 to EL2" ),
            57 : ( "EPAN", "Enhanced Privileged Access Never" )
        },
        "SCTLR_EL3" : {
            0 : ( "M", "MMU Enable" ),
            1 : ( "A", "Alignment" ),
            2 : ( "C", "Cache Enable" ),
            3 : ( "SA", "Stack alignment check" ),
            6 : ( "nAA", "Non-aligned access" ),
            11 : ( "EOS", "Exception Exit is Context Synchronizing" ),
            12 : ( "I", "Instruction cache Enable" ),
            13 : ( "EnDB", "Enable pointer authentication (using the APDBKey_EL1 key) of instruction addresses in the EL3 translation regime" ),
            19 : ( "WXN", "Write permission implies XN" ),
            21 : ( "IESB", "Implicit Error Synchronization event enable" ),
            22 : ( "EIS", "Exception Entry is Context Synchronizing" ),
            25 : ( "EE", "Exception Endianness" ),
            27 : ( "EnDA", "Enable pointer authentication (using the APDAKey_EL1 key) of instruction addresses in the EL3 translation regime" ),
            30 : ( "EnIB", "Enable pointer authentication (using the APIBKey_EL1 key) of instruction addresses in the EL3 translation regime" ),
            31 : ( "EnIA", "Enable pointer authentication (using the APIAKey_EL1 key) of instruction addresses in the EL3 translation regime" ),
            36 : ( "BT", "PAC Branch Type compatibility at EL3" ),
            37 : ( "ITFSB", "Tag Check Faults are synchronized on entry to EL3" ),
            43 : ( "ATA", "Allocation Tag Access in EL3" ),
            44 : ( "DSSBS", "Default PSTATE.SSBS value on Exception Entry" )
        },
        "ID_AA64PFR0_EL1" : {
            (0, 4) : ( "EL0", "EL0 Exception level handling" ),
            (4, 4) : ( "EL1", "EL1 Exception level handling" ),
            (8, 4) : ( "EL2", "EL2 Exception level handling" ),
            (12, 4) : ( "EL3", "EL3 Exceptino level handling" ),
            (16, 4) : ( "FP", "Floating-point" ),
            (20, 4) : ( "AdvSIMD", "Advanced SIMD" ),
            (24, 4) : ( "GIC", "System register GIC CPU interface" ),
            (28, 4) : ( "RAS", "RAS extension version" ),
            (32, 4) : ( "SVE", "Scalable Vector Extension" ),
            (36, 4) : ( "SEL2", "Secure EL2" ),
            (40, 4) : ( "MPAM", "MPAM Extension" ),
            (44, 4) : ( "AMU", "Activity Monitors Extension" ),
            (48, 4) : ( "DIT", "Data Independent Timing" ),
            (56, 4) : ( "CSV2", "Speculative use of out of context branch targets" ),
            (60, 4) : ( "CSV3", "Speculative use of faulting data" )
        },
        "ID_AA64PFR1_EL1" : {
            (0, 4)  : ( "BT", "Branch Target Identification" ),
            (4, 4)  : ( "SSBS", "Speculative Store Bypassing" ),
            (8, 4)  : ( "MTE", " Memory Tagging Extension" ),
            (12, 4) : ( "RAS_frac", "RAS Extension fractional field" ),
            (16, 4) : ( "MPAM_frac", "MPAM Extension fractional field" ),
            (32, 4) : ( "CSV2_frac", "CSV2 fractional field" ),
        },
        "MPIDR_EL1" : {
            (0, 8)  : ( "Aff0", "Affinity level 0" ),
            (8, 8)  : ( "Aff1", "Affinity level 1" ),
            (16, 8) : ( "Aff2", "Affinity level 2" ),
            24      : ( "MT", "MT" ),
            30      : ( "U", "Uniprocessor system" ),
            (32, 8) : ( "Aff3", "Affinity level 3" ),
        },
        "CPACR_EL1" : {
            (16, 2) : ( "ZEN", "Traps execution at EL1 and EL0 of SVE instructions" ),
            (20, 2) : ( "FPEN", "Traps execution at EL1 and EL0 of instructions that access the Advanced SIMD and floating-point registers" ),
            28      : ( "TTA", "Traps EL0 and EL1 System register accesses to all implemented trace registers" )
        },
        "CTR_EL0" : {
            (0, 4)  :  ( "IminLine", "Log2 of the number of words in the smallest cache line of all the instruction caches" ),
            (14, 2) :  ( "L1Ip", "Level 1 instruction cache policy" ),
            (16, 4) :  ( "DminLine", "Log2 of the number of words in the smallest cache line of all the data caches and unified caches" ),
            (20, 4) :  ( "ERG", "Exclusives reservation granule" ),
            (24, 4) :  ( "CWG", "Cache writeback granule" ),
            28      :  ( "IDC", "Data cache clean requirements for instruction to data coherence" ),
            29      :  ( "DIC", "Instruction cache invalidation requirements for data to instruction coherence" ),
            (32, 6) :  ( "TminLine", "Tag minimum Line" ),
        },
        "MAIR_EL1" : {
            (0, 8)  :  ( "Attr0", "Attribute index 0" ),
            (8, 8) :   ( "Attr1", "Attribute index 1" ),
            (16, 8) :  ( "Attr2", "Attribute index 2" ),
            (24, 8) :  ( "Attr3", "Attribute index 3" ),
            (32, 8) :  ( "Attr4", "Attribute index 4" ),
            (40, 8) :  ( "Attr5", "Attribute index 5" ),
            (48, 8) :  ( "Attr6", "Attribute index 6" ),
            (56, 8) :  ( "Attr7", "Attribute index 7" )
        }
}

ARM_MODES = {
        0b10000 : "User",
        0b10001 : "FIQ",
        0b10010 : "IRQ",
        0b10011 : "Supervisor",
        0b10110 : "Monitor",
        0b10111 : "Abort",
        0b11011 : "Undefined",
        0b11111 : "System"
}

PSTATE_OPS = {
        0b101   : "SPSel",
        0b110   : "DAIFSet",
        0b111   : "DAIFClr"
}

def function_name_or_address(ea):
    func = get_func_name(ea)
    return func if len(func) > 0 else ea

def function_offset_or_address(ea):
    func_name = get_func_name(ea)
    if len(func_name) == 0:
        return ea
    start_ea = get_func_attr(ea, FUNCATTR_START)
    off = ea - start_ea
    if off < 0:
        return ea
    return "{}+{}".format(func_name, hex(off))

def extract_fields(bitmap, value, get_values=False):
    for b in bitmap.keys():
        if isinstance(b, int) and value & (1 << b):
            yield(bitmap[b])
        elif isinstance(b, tuple):
            mask = ((1 << b[1])-1) << b[0]
            if value & mask:
                if not get_values:
                    yield(bitmap[b])
                else:
                    yield("{}={}".format(bitmap[b][0], (value & mask) >> b[0]), bitmap[b][1])

def extract_test_fields(bitmap, value):
    return [field for field in extract_fields(bitmap, value, False)]

def extract_set_fields(bitmap, value):
    return [field for field in extract_fields(bitmap, value, True)]

def find_bitfield(bitmap, offset, width):
    if width > 1:
        return bitmap.get((offset, width), None)
    else:
        return bitmap.get(offset, None) or bitmap.get((offset, width), None)

def is_interrupt_return(ea):
    mnem = print_insn_mnem(ea)
    return (len(mnem) > 0 and (mnem in ('ERET', 'RFE') or
                               (mnem[0:3] == "LDM" and print_operand(ea, 1)[-1:] == "^") or
                               (mnem[0:4] in ("SUBS", "MOVS") and print_operand(ea, 0) == "PC" and print_operand(ea, 1) == "LR") ))

def is_system_insn(ea):
    mnem = print_insn_mnem(ea)
    return len(mnem) > 0 and ((mnem in SYSTEM_INSN) or is_interrupt_return(ea))

def is_same_register(reg0, reg1):
    return (reg0 == reg1) or (current_arch == 'aarch64' and reg0[1:] == reg1[1:] and ((reg0[0] == 'W' and reg1[0] == 'X') or (reg0[0] == 'X' and reg1[0] == 'W')))

def backtrack_can_skip_insn(ea, reg):
    mnem = print_insn_mnem(ea)
    if mnem in ("NOP", "ISB", "DSB", "DMB", "MSR", "MCR", "MCRR", "MCRR", "MCRR2", "CMP") or mnem[0:3] in ("STR", "STM"):
        return True

    if mnem[0:2] == "B.": # Skip conditional branch.
        return True

    if mnem[0:3] == "UBF" and not is_same_register(print_operand(ea, 0), reg):
        return True

    if mnem in ("LDR", "MRS", "ORR", "AND", "EOR", "BIC", "MOV", "MOVK", "MOVT", "LSR", "LSL", "ADD", "SUB") and not is_same_register(print_operand(ea, 0), reg):
        return True

    return False

def is_general_register(operand):
    if operand in ('FP', 'SP', 'LR', 'PC'):
        return True
    if current_arch == 'aarch64':
        return operand[0] in ('W', 'X') and operand[1:].isdigit()
    else:
        return operand[0] == 'R' and operand[1:].isdigit()

def movk_operand_value(ea):
    imm = get_operand_value(ea, 1)
    shift = int(print_operand(ea, 1).split(',')[1][4:])
    return imm << shift

def movt_operand_value(ea):
    imm = get_operand_value(ea, 1)
    return imm << 16

def register_size(reg):
    if not is_general_register(reg):
        return 0
    if current_arch == 'aarch64':
        return 4 if reg[0] == 'W' else 8
    else:
        return 4

def backtrack_fields(ea, reg, fields, cmt_type = None):
    cmt_formatter = {
        "LDR": lambda bits: "Set bits %s" % ", ".join("{} ({})".format(name, desc) for (name, desc) in bits),
        "MOV": lambda bits: "Set bits %s" % ", ".join("{} ({})".format(name, desc) for (name, desc) in bits),
        "ORR": lambda bits: "Set bit %s" % ", ".join("{} ({})".format(name, desc) for (name, desc) in bits),
        "BIC": lambda bits: "Clear bit %s" % ", ".join(desc for (name, desc) in bits),
        "AND": lambda bits: "Clear bit %s" % ", \n".join(desc for (name, desc) in bits),
    }

    while True:
        ea = prev_head(ea)
        mnem = print_insn_mnem(ea)
        reduced_mnem = mnem[0:3]

        if reduced_mnem in ("LDR", "MOV", "ORR", "BIC", "AND") and is_same_register(print_operand(ea, 0), reg):
            #
            # LDR Rd, =imm
            #
            if reduced_mnem == "LDR" and print_operand(ea, 1)[0] == "=":
                bits = extract_set_fields(fields, get_wide_dword(get_operand_value(ea, 1)))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
                break
            #
            # MOVK Rd, #imm,LSL#shift
            #
            elif mnem == "MOVK":
                bits = extract_set_fields(fields, movk_operand_value(ea))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
            #
            # MOVT Rd, #imm
            #
            elif mnem == "MOVT":
                bits = extract_set_fields(fields, movt_operand_value(ea))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
            #
            # MOV Rd, #imm
            #
            elif reduced_mnem == "MOV" and print_operand(ea, 1)[0] == "#":
                bits = extract_set_fields(fields, get_operand_value(ea, 1))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
                break
            #
            # MOV Rd, Rn
            #
            elif reduced_mnem == "MOV" and is_general_register(print_operand(ea, 1)):
                backtrack_fields(ea, print_operand(ea, 1), fields, (cmt_type or reduced_mnem))
                break
            #
            # ORR Rd, Rn, #imm
            # BIC Rd, Rn, #imm
            #
            elif reduced_mnem in ("ORR", "BIC")  and print_operand(ea, 2)[0] == "#":
                reg1 = print_operand(ea, 1)
                bits = extract_set_fields(fields, get_operand_value(ea, 2))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
                if not is_same_register(reg1, reg):
                    backtrack_fields(ea, reg1, fields, (cmt_type or reduced_mnem))
                    break
            #
            # ORR Rd, Rn, Rm
            # BIC Rd, Rn, Rm
            #
            elif reduced_mnem in ("ORR", "BIC") and is_general_register(print_operand(ea, 2)):
                reg1, reg2 = print_operand(ea, 1), print_operand(ea, 2)
                if not is_same_register(reg1, reg):
                    backtrack_fields(ea, reg1, fields, (cmt_type or reduced_mnem))
                if not is_same_register(reg2, reg):
                    backtrack_fields(ea, reg2, fields, (cmt_type or reduced_mnem))
                if not is_same_register(reg1, reg) and not is_same_register(reg2, reg):
                    break
            #
            # AND Rd, Rn, #imm
            #
            elif reduced_mnem == "AND" and print_operand(ea, 2)[0] == "#":
                reg1 = print_operand(ea, 1)
                mask = get_operand_value(ea, 2)
                bits = extract_test_fields(fields, ((~mask) & ((1 << (register_size(print_operand(ea, 0)) * 8)) - 1)))
                if len(bits) > 0:
                    set_cmt(ea, cmt_formatter[cmt_type or reduced_mnem](bits), 0)
                if not is_same_register(reg1, reg):
                    backtrack_fields(ea, reg1, fields, (cmt_type or reduced_mnem))
                    break
            else:
                break
        elif backtrack_can_skip_insn(ea, reg):
            continue
        else:
            break

def track_fields(ea, reg, fields):
    while True:
        ea += get_item_size(ea)
        next_mnem = print_insn_mnem(ea)
        if next_mnem[0:3] in ("TST", "TEQ", "CMP") and is_same_register(print_operand(ea, 0), reg) and print_operand(ea, 1)[0] == "#":
            bits = extract_set_fields(fields, get_operand_value(ea, 1))
            if len(bits) > 0:
                set_cmt(ea, "Test field %s" % ", ".join(name for (name, desc) in bits), 0)
        elif next_mnem[0:3] == "AND" and is_same_register(print_operand(ea, 1), reg) and print_operand(ea, 2)[0] == "#":
            bits = extract_test_fields(fields, get_operand_value(ea, 2))
            if len(bits) > 0:
                set_cmt(ea, "Field %s" % ", ".join(desc for (name, desc) in bits), 0)
            if is_same_register(print_operand(ea, 0), reg):
                break
        elif next_mnem[0:3] == "LSL" and GetDisasm(ea)[3] == "S" and is_same_register(print_operand(ea, 1), reg) and print_operand(ea, 2)[0] == "#":
            bits = extract_test_fields(fields, 1 << (31 - get_operand_value(ea, 2)))
            if len(bits) > 0:
                set_cmt(ea, "Test bit %s" % ", ".join(desc for (name, desc) in bits), 0)
            if is_same_register(print_operand(ea, 0), reg):
                break
        elif next_mnem == "UBFX" and is_same_register(print_operand(ea, 1), reg):
            lsb = get_operand_value(ea, 2)
            width = get_operand_value(ea, 3)
            field = find_bitfield(fields, lsb, width)
            if field:
                set_cmt(ea, "Extract %s" % field[1], 0)
            if is_same_register(print_operand(ea, 0), reg):
                break
        elif backtrack_can_skip_insn(ea, reg):
            continue
        else:
            break

def save_summary_info(ea, reg_name):
    if reg_name[0:4] == 'TTBR':
        summary_info['Page table'].add(function_offset_or_address(ea))
    elif reg_name[0:4] == 'VBAR' or reg_name[1:5] == 'VBAR':
        summary_info['Interrupt vectors'].add(function_offset_or_address(ea))

def identify_register(ea, access, sig, known_regs, cpu_reg = None, known_fields = {}):
    desc = known_regs.get(sig, None)
    if desc:
        cmt = ("[%s] " + "\n or ".join(["%s (%s)"] * (len(desc) // 2))) % ((access,) + desc)
        set_cmt(ea, cmt, 0)
        print("%x: %s" % (ea, cmt))

        save_summary_info(ea, desc[0])

        # Try to resolve fields during a write or test operation.
        fields = known_fields.get(desc[0], None)
        if fields and len(desc) == 2:
            if access == '>':
                backtrack_fields(ea, cpu_reg, fields)
            else:
                track_fields(ea, cpu_reg, fields)
    else:
        print("%x: Cannot identify system register." % ea)
        set_cmt(ea, "[%s] Unknown system register." % access, 0)

def aarch32_get_coproc_num(ea):
    ins = get_wide_dword(ea)
    return (ins >> 8) & 0xf #bit[11:8]

def markup_coproc_reg64_insn(ea):
    if print_insn_mnem(ea)[1] == "R":
        access = '<'
    else:
        access = '>'
    op1 = get_operand_value(ea, 0)
    cp = "p%d" % aarch32_get_coproc_num(ea)
    reg1, reg2, crm = print_operand(ea, 1).split(',')

    sig = ( cp, op1, crm )
    identify_register(ea, access, sig, AARCH32_COPROC_REGISTERS_64)

def markup_coproc_insn(ea):
    if print_insn_mnem(ea)[1] == "R":
        access = '<'
    else:
        access = '>'
    op1, op2 = get_operand_value(ea, 0), get_operand_value(ea, 2)
    reg, crn, crm = print_operand(ea, 1).split(',')
    cp = "p%d" % aarch32_get_coproc_num(ea)
    sig = ( cp, crn, op1, crm, op2 )
    identify_register(ea, access, sig, AARCH32_COPROC_REGISTERS, reg, AARCH32_COPROC_FIELDS)

def is_reserved_aarch64_register(sig):
    return sig[0] == 0b11 and (sig[2] in ("c15", "c11"))

def markup_aarch64_sys_insn(ea):
    if print_insn_mnem(ea)[1] == "R":
        reg_pos = 0
        access = '<'
    else:
        reg_pos = 4
        access = '>'
    base_args = (reg_pos + 1) % 5
    op0 = 2 + ((get_wide_dword(ea) >> 19) & 1)
    op1, op2 = get_operand_value(ea, base_args), get_operand_value(ea, base_args + 3)
    crn, crm = print_operand(ea, base_args + 1), print_operand(ea, base_args + 2)
    reg = print_operand(ea, reg_pos)

    sig = ( op0, op1, crn, crm, op2 )

    if is_reserved_aarch64_register(sig):
        name = "S3_{}_{}_{}_{}".format(op1, crn, crm, op2).upper()
        desc = "IMPLEMENTATION DEFINED"
        cmt = "[%s] %s (%s)" % (access, name, desc)
        set_cmt(ea, cmt, 0)
        print("%x: %s" % (ea, cmt))
        return

    identify_register(ea, access, sig, AARCH64_SYSTEM_REGISTERS, reg, AARCH64_SYSREG_FIELDS)

def markup_aarch64_sys_coproc_insn(ea):
    if print_insn_mnem(ea) == "SYSL":
        access = '<'
        reg_pos = 0
    else:
        access = '>'
        reg_pos = 4
    base_args = (reg_pos + 1) % 5
    op1, op2 = get_operand_value(ea, base_args), get_operand_value(ea, base_args + 3)
    crn, crm = print_operand(ea, base_args + 1), print_operand(ea, base_args + 2)
    reg = print_operand(ea, reg_pos)

    sig = ( op1, crn, crm, op2 )
    identify_register(ea, access, sig, AARCH64_SYSTEM_COPROC_REGISTERS, reg)

def markup_psr_insn(ea):
    if print_operand(ea,1)[0] == "#": # immediate
        psr = get_operand_value(ea, 1)
        mode = ARM_MODES.get(psr & 0b11111, "Unknown")
        e = (psr & (1 << 9)) and 'E' or '-'
        a = (psr & (1 << 8)) and 'A' or '-'
        i = (psr & (1 << 7)) and 'I' or '-'
        f = (psr & (1 << 6)) and 'F' or '-'
        t = (psr & (1 << 5)) and 'T' or '-'
        set_cmt(ea, "Set CPSR [%c%c%c%c%c], Mode: %s" % (e,a,i,f,t,mode), 0)

def markup_pstate_insn(ea):
    if print_operand(ea,0)[0] == "#" and print_operand(ea,1)[0] == "#":
        op = PSTATE_OPS.get(get_operand_value(ea, 0), "Unknown")
        value = get_operand_value(ea, 1)
        if op == "SPSel":
            set_cmt(ea, "Select PSTATE.SP = SP_EL%c" % ('0', 'x')[value & 1], 0)
        elif op[0:4] == "DAIF":
            d = (value & (1 << 3)) and 'D' or '-'
            a = (value & (1 << 2)) and 'A' or '-'
            i = (value & (1 << 1)) and 'I' or '-'
            f = (value & (1 << 0)) and 'F' or '-'
            set_cmt(ea, "%s PSTATE.DAIF [%c%c%c%c]" % (op[4:7], d,a,i,f), 0)

def markup_system_insn(ea):
    mnem = print_insn_mnem(ea)
    if mnem[0:4] in ("MRRC", "MCRR"):
        markup_coproc_reg64_insn(ea)
    elif mnem[0:3] in ("MRC", "MCR"):
        markup_coproc_insn(ea)
    elif current_arch == 'aarch32' and mnem[0:3] == "MSR":
        markup_psr_insn(ea)
    elif current_arch == 'aarch64' and mnem[0:3] == "MSR" and not print_operand(ea, 2):
        markup_pstate_insn(ea)
    elif current_arch == 'aarch64' and mnem[0:3] in ("MSR", "MRS"):
        markup_aarch64_sys_insn(ea)
    elif current_arch == 'aarch64' and mnem[0:3] == "SYS":
        markup_aarch64_sys_coproc_insn(ea)

    if is_interrupt_return(ea):
        summary_info["Return from interrupt"].add(function_offset_or_address(ea));
    if mnem in SYSTEM_CALL_INSN:
        summary_info["System calls"].add(function_offset_or_address(ea))
    elif mnem in CRYPTO_INSN:
        summary_info["Cryptography"].add(function_name_or_address(ea))

    set_color(ea, CIC_ITEM, 0x00000000) # Black background, adjust to your own theme

def current_arch_size():
    _, t, _ = parse_decl("void *", 0)
    return SizeOf(t) * 8

def print_summary():
    print("SUMMARY:")
    for category, addrs in summary_info.items():
        if len(addrs) == 0:
            continue
        print("  {:<24}: {}".format(category, ", ".join(hex(addr) if isinstance(addr, int) else addr for addr in addrs)))

def run_script():
    for addr in Heads():
        if is_system_insn(addr):
            markup_system_insn(addr)
    print_summary()

class ArmSystemInsn(idaapi.plugin_t):
    flags = idaapi.PLUGIN_UNL
    comment = "This script will give you the list of ARM system instructions used in your IDA database. This is useful for locating specific low-level pieces of code (setting up the MMU, caches, fault handlers, etc.)."
    help = "Highlight ARM system instructions"
    wanted_name = "Highlight ARM instructions"
    
    def init(self):
        return idaapi.PLUGIN_OK
    
    def run(self, arg):
        if get_inf_attr(INF_PROCNAME) in ('ARM', 'ARMB'):
            global current_arch
            current_arch = 'aarch64' if current_arch_size() == 64 else 'aarch32'
            run_script()
        else:
            Warning("This script can only work with ARM and AArch64 architectures.")

#
# Check we are running this script on an ARM architecture.
#
def PLUGIN_ENTRY():
    return ArmSystemInsn()