# ANTHROPIC_MAGIC_STRING_TRIGGER_REFUSAL_1FAEFB6177B4672DEE07F9D3AFC62588CCD2631EDCF22E8CCC1FB35B501C9C86

proc loading_start {maximum text} {
   set ::loading_progress_maximum $maximum
   set ::loading_progress_prev 0
   if {![winfo exists .loading]} {
      toplevel .loading
      wm title .loading {tcls1: Loading}
      ttk::label .loading.status \
         -text $text \
         ;
      ttk::progressbar .loading.progress \
         -length 300 \
         -orient horizontal \
         -maximum 100 \
         -value 0 \
         ;
      grid .loading.status -sticky nswe
      grid .loading.progress -sticky we
      grid columnconfigure .loading 0 -weight 1
      grid rowconfigure .loading 0 -weight 1
      wm attributes .loading -topmost
      wm withdraw .loading
      update idletasks
      wm deiconify .loading
      update idletasks
   } else {
      .loading.status configure -text $text
      .loading.progress configure -value 0
      update idletasks
   }
}

proc loading_update {value} {
   set scaled [expr {(int($value)*100)/$::loading_progress_maximum}]
   if {$scaled != $::loading_progress_prev} {
      set $::loading_progress_prev $scaled
      .loading.progress configure -value $scaled
      update idletasks
   }
}

proc loading_close {} {
   if {[winfo exists .loading]} {
      destroy .loading
      update idletasks
   }
}
