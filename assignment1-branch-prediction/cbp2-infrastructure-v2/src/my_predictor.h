// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a global predictor. 
//
// Structure (see the Pentium M diagram in the assignment):
//   - Bimodal table: 4096 2-bit counters, index = IP[11:0].
//   - Global predictor: 512 sets x PM_GLOBAL_WAYS ways. Each entry has a
//     valid bit, a 6-bit tag, a 2-bit counter and an LRU stamp.
//     HASH = IP[14:0] XOR GHR[14:0]; index = HASH[14:6], tag = HASH[5:0].
//     (The real Pentium M hashes the IP with a path information register;
//     the assignment lets us skip the PIR, so a global history register of
//     conditional-branch outcomes is used instead.)
//   - Final prediction: global prediction on a tag hit, bimodal otherwise.
//
// Update policy:
//   - The bimodal counter is always trained.
//   - On a global hit the global counter is trained and the way becomes MRU.
//   - On a global miss a new entry is allocated (LRU victim) only when the
//     bimodal predictor was wrong, so the global table holds only branches
//     the bimodal table cannot handle. Define PM_ALLOCATE_ALWAYS to allocate
//     on every miss instead (the policy used in the Appendix B example).

#ifndef PM_GLOBAL_WAYS
#define PM_GLOBAL_WAYS		4	// the assignment also allows 2
#endif
#define PM_BIMODAL_BITS		12	// 4096 entries
#define PM_GLOBAL_INDEX_BITS	9	// 512 sets
#define PM_GLOBAL_TAG_BITS	6
#define PM_HASH_BITS		(PM_GLOBAL_INDEX_BITS + PM_GLOBAL_TAG_BITS)	// 15

struct pm_global_entry {
	bool valid;
	unsigned char tag;
	unsigned char ctr;		// 2-bit saturating counter
	unsigned int lru;		// larger = more recently used
};

class pm_update : public branch_update {
public:
        unsigned int index;		// bimodal index
        unsigned int set;		// global set
        unsigned int tag;		// global tag
        int way;			// hit way, -1 on a global miss
        bool bimodal_prediction;
};

class pm_predictor : public branch_predictor {
public:
        pm_update u;
        branch_info bi;
        unsigned int history;
        unsigned int lru_clock;
        unsigned char bimodal[1<<PM_BIMODAL_BITS];
        pm_global_entry global[1<<PM_GLOBAL_INDEX_BITS][PM_GLOBAL_WAYS];

        pm_predictor (void) : history(0), lru_clock(0) {
		// counters start weakly not-taken; the global table starts empty
		memset (bimodal, 1, sizeof (bimodal));
		memset (global, 0, sizeof (global));
        }

        branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			// bimodal lookup
			u.index = b.address & ((1<<PM_BIMODAL_BITS)-1);
			u.bimodal_prediction = bimodal[u.index] >> 1;

			// global lookup
			unsigned int hash = (b.address ^ history) & ((1<<PM_HASH_BITS)-1);
			u.set = hash >> PM_GLOBAL_TAG_BITS;
			u.tag = hash & ((1<<PM_GLOBAL_TAG_BITS)-1);
			u.way = -1;
			for (int w = 0; w < PM_GLOBAL_WAYS; w++) {
				pm_global_entry &e = global[u.set][w];
				if (e.valid && e.tag == u.tag) {
					u.way = w;
					break;
				}
			}

			// global hit overrides the bimodal prediction
			if (u.way >= 0)
				u.direction_prediction (global[u.set][u.way].ctr >> 1);
			else
				u.direction_prediction (u.bimodal_prediction);
		} else {
			u.direction_prediction (true);
		}
		// branch target prediction is not required
		u.target_prediction (0);
		return &u;
        }

        void update (branch_update *bu, bool taken, unsigned int target) {
		if (!(bi.br_flags & BR_CONDITIONAL)) return;
		pm_update *p = (pm_update *) bu;

		// bimodal table is always trained
		train (bimodal[p->index], taken);

		if (p->way >= 0) {
			pm_global_entry &e = global[p->set][p->way];
			train (e.ctr, taken);
			e.lru = ++lru_clock;
		} else {
#ifndef PM_ALLOCATE_ALWAYS
			if (p->bimodal_prediction != taken)
#endif
				allocate (p->set, p->tag, taken);
		}

		history = ((history << 1) | taken) & ((1<<PM_HASH_BITS)-1);
        }

        // replace an invalid way if there is one, otherwise the LRU way
        void allocate (unsigned int set, unsigned int tag, bool taken) {
		int victim = 0;
		for (int w = 0; w < PM_GLOBAL_WAYS; w++) {
			if (!global[set][w].valid) { victim = w; break; }
			if (global[set][w].lru < global[set][victim].lru) victim = w;
		}
		pm_global_entry &e = global[set][victim];
		e.valid = true;
		e.tag = tag;
		e.ctr = taken ? 2 : 1;		// weakly toward the actual outcome
		e.lru = ++lru_clock;
        }

        static void train (unsigned char &c, bool taken) {
		if (taken) {
			if (c < 3) c++;
		} else {
			if (c > 0) c--;
		}
        }
};

//
// Complete Pentium M branch predictors for extra credit
// This class implements the complete Pentium M branch prediction units. 
// It implements both branch target prediction and branch outcome predicton. 
class cpm_update : public branch_update {
public:
        unsigned int index;
};

class cpm_predictor : public branch_predictor {
public:
        cpm_update u;

        cpm_predictor (void) {
        }

        branch_update *predict (branch_info & b) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *u, bool taken, unsigned int target) {
        }

};


